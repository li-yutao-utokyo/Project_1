from __future__ import annotations

import datetime

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.analysis import run as run_module
from src.analysis.optimize_r import find_optimal_r, optimize_r
from src.analysis.wind_comfort import (
    classify_uncomfortable_days,
    daily_max_pedestrian_wind_speed,
    pedestrian_wind_speed,
    wind_direction_temperature_stats,
)
from src.storage.models import Base, ProcessedObservation, RWindOptimizationResult


def _obs(hour_offset_days: int, hour: int, **overrides) -> dict:
    base = {
        "timestamp": datetime.datetime(2024, 6, 1, hour, 0, tzinfo=datetime.UTC)
        + datetime.timedelta(days=hour_offset_days),
        "wind_speed": 2.0,
        "wind_direction_octant": "N",
        "temperature": 20.0,
    }
    base.update(overrides)
    return base


# ---- wind_comfort ----------------------------------------------------------


def test_pedestrian_wind_speed_multiplies_by_r():
    df = pd.DataFrame([_obs(0, 0, wind_speed=2.0), _obs(0, 1, wind_speed=4.0)])
    result = pedestrian_wind_speed(df, r=2.0)
    assert list(result["pedestrian_wind_speed"]) == [4.0, 8.0]


def test_daily_max_pedestrian_wind_speed_groups_by_date():
    df = pd.DataFrame(
        [
            _obs(0, 0, wind_speed=2.0),
            _obs(0, 1, wind_speed=6.0),
            _obs(1, 0, wind_speed=3.0),
        ]
    )
    daily_max = daily_max_pedestrian_wind_speed(pedestrian_wind_speed(df, r=1.0))
    assert daily_max[datetime.date(2024, 6, 1)] == 6.0
    assert daily_max[datetime.date(2024, 6, 2)] == 3.0


def test_classify_uncomfortable_days_flags_strong_and_weak_days():
    df = pd.DataFrame(
        [
            _obs(0, 0, wind_speed=6.0),  # day 1: strong (max 6 > 5)
            _obs(1, 0, wind_speed=0.5),  # day 2: weak (max 0.5 < 1)
            _obs(2, 0, wind_speed=3.0),  # day 3: neither
        ]
    )
    result = classify_uncomfortable_days(df, r=1.0)
    assert result.loc[datetime.date(2024, 6, 1), "strong_wind_day"]
    assert not result.loc[datetime.date(2024, 6, 1), "weak_wind_day"]
    assert result.loc[datetime.date(2024, 6, 2), "weak_wind_day"]
    assert not result.loc[datetime.date(2024, 6, 2), "strong_wind_day"]
    assert not result.loc[datetime.date(2024, 6, 3), "strong_wind_day"]
    assert not result.loc[datetime.date(2024, 6, 3), "weak_wind_day"]


def test_wind_direction_temperature_stats_groups_by_octant():
    df = pd.DataFrame(
        [
            _obs(0, 0, wind_direction_octant="N", temperature=10.0),
            _obs(0, 1, wind_direction_octant="N", temperature=20.0),
            _obs(0, 2, wind_direction_octant="E", temperature=30.0),
        ]
    )
    stats = wind_direction_temperature_stats(df)
    assert stats.loc["N", "mean"] == 15.0
    assert stats.loc["N", "count"] == 2
    assert stats.loc["E", "mean"] == 30.0
    assert pd.isna(stats.loc["SW", "mean"])  # octant absent from the sample


# ---- optimize_r -------------------------------------------------------------


def test_optimize_r_all_comfortable_gives_zero_total_days():
    # day A never crosses the strong threshold (10*R <= 5.0 for R in [0.3, 0.5])
    # day B never crosses the weak threshold (4*R >= 1.0 for R in [0.3, 0.5])
    df = pd.DataFrame([_obs(0, 0, wind_speed=10.0), _obs(1, 0, wind_speed=4.0)])
    curve = optimize_r(df, r_min=0.3, r_max=0.5, r_step=0.05)
    assert list(curve.columns) == ["r", "strong_wind_days", "weak_wind_days", "total_days"]
    assert (curve["total_days"] == 0).all()


def test_optimize_r_u_shape_minimum_between_the_extremes():
    # day A: strong once R > 0.625 (5/8); day B: weak only while R < 1/3
    df = pd.DataFrame([_obs(0, 0, wind_speed=8.0), _obs(1, 0, wind_speed=3.0)])
    curve = optimize_r(df, r_min=0.3, r_max=1.0, r_step=0.05)

    assert curve.iloc[0]["total_days"] == 1  # r=0.30: day B still weak
    assert curve.iloc[-1]["total_days"] == 1  # r=1.00: day A now strong
    assert curve["total_days"].min() == 0
    optimal = find_optimal_r(curve)
    assert optimal["total_days"] == 0
    assert 0.3 < optimal["r"] < 1.0


def test_optimize_r_strong_plus_weak_equals_total_for_every_row():
    df = pd.DataFrame([_obs(0, 0, wind_speed=100.0), _obs(1, 0, wind_speed=0.1)])
    curve = optimize_r(df, r_min=0.3, r_max=1.0, r_step=0.1)
    assert (curve["strong_wind_days"] + curve["weak_wind_days"] == curve["total_days"]).all()
    assert (curve["total_days"] == 2).all()  # always uncomfortable on both fronts


def test_find_optimal_r_breaks_ties_on_smallest_r():
    result = pd.DataFrame(
        {
            "r": [0.4, 0.5, 0.6],
            "total_days": [3, 1, 1],
            "strong_wind_days": [2, 1, 0],
            "weak_wind_days": [1, 0, 1],
        }
    )
    optimal = find_optimal_r(result)
    assert optimal["r"] == 0.5


# ---- analysis.run end-to-end -------------------------------------------------


def test_analysis_run_persists_curve_and_returns_optimal(monkeypatch: pytest.MonkeyPatch):
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all(
            [
                ProcessedObservation(
                    city="tokyo", source="open-meteo", **_obs(0, 0, wind_speed=10.0)
                ),
                ProcessedObservation(
                    city="tokyo", source="open-meteo", **_obs(1, 0, wind_speed=4.0)
                ),
            ]
        )
        session.commit()

    optimal, curve = run_module.run(
        "tokyo",
        datetime.date(2024, 6, 1),
        datetime.date(2024, 6, 2),
        r_min=0.3,
        r_max=0.5,
        r_step=0.05,
        engine=engine,
    )

    assert optimal is not None
    assert optimal["total_days"] == 0
    assert len(curve) == 5  # 0.30, 0.35, 0.40, 0.45, 0.50

    with Session(engine) as session:
        rows = session.query(RWindOptimizationResult).all()
    assert len(rows) == 5
    assert all(row.city == "tokyo" for row in rows)

    # re-running the same range should replace, not duplicate, the rows
    run_module.run(
        "tokyo",
        datetime.date(2024, 6, 1),
        datetime.date(2024, 6, 2),
        r_min=0.3,
        r_max=0.5,
        r_step=0.05,
        engine=engine,
    )
    with Session(engine) as session:
        rows = session.query(RWindOptimizationResult).all()
    assert len(rows) == 5


def test_analysis_run_returns_none_for_empty_range():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    optimal, df = run_module.run(
        "tokyo", datetime.date(2024, 1, 1), datetime.date(2024, 1, 2), engine=engine
    )
    assert optimal is None
    assert df.empty
