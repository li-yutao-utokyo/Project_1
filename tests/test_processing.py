from __future__ import annotations

import datetime

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.processing import run as run_module
from src.processing.clean import clean, drop_duplicates, drop_missing_required, filter_outliers
from src.processing.transform import classify_wind_direction_octant, transform
from src.storage.models import Base, ProcessedObservation, RawObservation


def _row(**overrides):
    base = {
        "city": "tokyo",
        "timestamp": datetime.datetime(2024, 6, 1, 0, 0, tzinfo=datetime.UTC),
        "wind_speed": 2.5,
        "wind_direction": 90.0,
        "temperature": 20.0,
        "humidity": 60.0,
        "source": "open-meteo",
    }
    base.update(overrides)
    return base


def test_drop_duplicates_keeps_last_row_per_key():
    df = pd.DataFrame([_row(wind_speed=1.0), _row(wind_speed=2.0)])
    result = drop_duplicates(df)
    assert len(result) == 1
    assert result.iloc[0]["wind_speed"] == 2.0


def test_drop_missing_required_drops_rows_without_wind_speed_or_temperature():
    df = pd.DataFrame([_row(), _row(wind_speed=None), _row(temperature=None)])
    result = drop_missing_required(df)
    assert len(result) == 1


def test_filter_outliers_drops_negative_wind_speed_and_out_of_range_values():
    df = pd.DataFrame(
        [
            _row(),
            _row(wind_speed=-1.0),  # physically impossible
            _row(temperature=999.0),  # out of range
            _row(wind_direction=400.0),  # out of range
        ]
    )
    result = filter_outliers(df)
    assert len(result) == 1


def _at(hour: int, **overrides):
    return _row(timestamp=datetime.datetime(2024, 6, 1, hour, 0, tzinfo=datetime.UTC), **overrides)


def test_clean_pipeline_on_dirty_sample():
    dirty = pd.DataFrame(
        [
            _at(0),
            _at(0),  # exact duplicate of the row above (same city/timestamp/source)
            _at(1, wind_speed=-3.0),  # outlier, dropped
            _at(2, temperature=None),  # missing required field, dropped
            _at(3, wind_direction=None),  # missing direction is allowed, not an outlier
        ]
    )
    result = clean(dirty)
    # one deduped good row (hour 0) + the row with a missing (but not out-of-range) direction
    assert len(result) == 2
    assert sorted(result["timestamp"].dt.hour) == [0, 3]


@pytest.mark.parametrize(
    "direction,expected",
    [(0, "N"), (46, "NE"), (90, "E"), (180, "S"), (270, "W"), (359, "N")],
)
def test_classify_wind_direction_octant(direction, expected):
    df = pd.DataFrame([_row(wind_direction=float(direction))])
    result = classify_wind_direction_octant(df)
    assert result.iloc[0]["wind_direction_octant"] == expected


def test_transform_standardizes_and_classifies():
    df = pd.DataFrame([_row(wind_direction=90.0)])
    result = transform(df)
    assert result.iloc[0]["wind_direction_octant"] == "E"
    assert result.iloc[0]["timestamp"].tzinfo is not None


def test_processing_run_writes_clean_processed_rows(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                RawObservation(**_at(0)),
                RawObservation(**_at(0)),  # duplicate, should collapse to one
                RawObservation(**_at(1, wind_speed=-5.0)),  # outlier, should be dropped
            ]
        )
        session.commit()

    count = run_module.run(
        "tokyo", datetime.date(2024, 6, 1), datetime.date(2024, 6, 1), engine=engine
    )

    assert count == 1
    with Session(engine) as session:
        rows = session.query(ProcessedObservation).all()
    assert len(rows) == 1
    assert rows[0].wind_direction_octant == "E"
