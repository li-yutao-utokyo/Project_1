from __future__ import annotations

import datetime

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.ingestion import run as run_module
from src.ingestion.openmeteo_client import (
    UnknownCityError,
    fetch_historical_weather,
    parse_openmeteo_response,
)
from src.storage.models import Base, RawObservation

SAMPLE_PAYLOAD = {
    "hourly": {
        "time": ["2024-06-01T00:00", "2024-06-01T01:00"],
        "wind_speed_10m": [2.5, 3.1],
        "wind_direction_10m": [180.0, 190.0],
        "temperature_2m": [22.0, 21.5],
        "relative_humidity_2m": [60.0, 62.0],
    }
}


def test_parse_openmeteo_response_maps_hourly_arrays_to_rows():
    records = parse_openmeteo_response(SAMPLE_PAYLOAD, city="tokyo")

    assert len(records) == 2
    assert records[0] == {
        "city": "tokyo",
        "timestamp": datetime.datetime(2024, 6, 1, 0, 0, tzinfo=datetime.UTC),
        "wind_speed": 2.5,
        "wind_direction": 180.0,
        "temperature": 22.0,
        "humidity": 60.0,
        "source": "open-meteo",
    }


def test_parse_openmeteo_response_handles_missing_hourly_key():
    assert parse_openmeteo_response({}, city="tokyo") == []


def test_fetch_historical_weather_unknown_city_raises():
    with pytest.raises(UnknownCityError):
        fetch_historical_weather("atlantis", datetime.date(2024, 6, 1), datetime.date(2024, 6, 1))


def test_fetch_historical_weather_builds_request_and_parses_json():
    captured_requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json=SAMPLE_PAYLOAD)

    mock_client = httpx.Client(transport=httpx.MockTransport(handler))

    payload = fetch_historical_weather(
        "tokyo", datetime.date(2024, 6, 1), datetime.date(2024, 6, 2), client=mock_client
    )

    assert payload == SAMPLE_PAYLOAD
    assert len(captured_requests) == 1
    params = dict(httpx.QueryParams(captured_requests[0].url.query.decode()))
    assert params["latitude"] == "35.6895"
    assert params["start_date"] == "2024-06-01"
    assert params["end_date"] == "2024-06-02"


def test_run_fetches_parses_and_persists_records(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(run_module, "fetch_historical_weather", lambda *a, **k: SAMPLE_PAYLOAD)

    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)

    count = run_module.run(
        "tokyo", datetime.date(2024, 6, 1), datetime.date(2024, 6, 1), engine=engine
    )

    assert count == 2
    with Session(engine) as session:
        rows = session.query(RawObservation).order_by(RawObservation.timestamp).all()
    assert [row.wind_speed for row in rows] == [2.5, 3.1]
    assert all(row.city == "tokyo" and row.source == "open-meteo" for row in rows)
