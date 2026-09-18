from __future__ import annotations

import datetime
import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://archive-api.open-meteo.com/v1/archive"

# MVP covers a handful of representative cities rather than every JMA station
# (see README §2.2 non-goals). Extend this table as more cities are added.
CITY_COORDINATES: dict[str, tuple[float, float]] = {
    "tokyo": (35.6895, 139.6917),
    "osaka": (34.6937, 135.5023),
    "nagoya": (35.1815, 136.9066),
}

HOURLY_VARIABLES = [
    "wind_speed_10m",
    "wind_direction_10m",
    "temperature_2m",
    "relative_humidity_2m",
]


class UnknownCityError(ValueError):
    """Raised when a requested city is not in CITY_COORDINATES."""


def _base_url() -> str:
    return os.environ.get("OPENMETEO_BASE_URL", DEFAULT_BASE_URL)


def fetch_historical_weather(
    city: str,
    start: datetime.date,
    end: datetime.date,
    *,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """Fetch raw hourly weather JSON for `city` between `start` and `end` (inclusive)."""
    city_key = city.strip().lower()
    if city_key not in CITY_COORDINATES:
        known = ", ".join(sorted(CITY_COORDINATES))
        raise UnknownCityError(f"Unknown city {city!r}. Known cities: {known}")
    latitude, longitude = CITY_COORDINATES[city_key]

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "hourly": ",".join(HOURLY_VARIABLES),
        "timezone": "UTC",
        "wind_speed_unit": "ms",
    }

    owns_client = client is None
    http_client = client or httpx.Client(timeout=30.0)
    try:
        response = http_client.get(_base_url(), params=params)
        response.raise_for_status()
        return response.json()
    finally:
        if owns_client:
            http_client.close()


def parse_openmeteo_response(
    payload: dict[str, Any], *, city: str, source: str = "open-meteo"
) -> list[dict[str, Any]]:
    """Turn an Open-Meteo `hourly` payload into a list of raw_observations rows."""
    hourly = payload.get("hourly", {})
    timestamps = hourly.get("time", [])
    wind_speeds = hourly.get("wind_speed_10m", [])
    wind_directions = hourly.get("wind_direction_10m", [])
    temperatures = hourly.get("temperature_2m", [])
    humidities = hourly.get("relative_humidity_2m", [])

    records = []
    for i, ts in enumerate(timestamps):
        records.append(
            {
                "city": city,
                "timestamp": datetime.datetime.fromisoformat(ts).replace(
                    tzinfo=datetime.UTC
                ),
                "wind_speed": wind_speeds[i] if i < len(wind_speeds) else None,
                "wind_direction": wind_directions[i] if i < len(wind_directions) else None,
                "temperature": temperatures[i] if i < len(temperatures) else None,
                "humidity": humidities[i] if i < len(humidities) else None,
                "source": source,
            }
        )
    return records
