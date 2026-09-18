from __future__ import annotations

import pandas as pd

# Per-source multiplier to standardize wind speed to m/s. Open-Meteo is
# requested with wind_speed_unit=ms already; a future non-metric source
# (e.g. one reporting km/h) would get its factor added here.
WIND_SPEED_TO_MS = {
    "open-meteo": 1.0,
}

OCTANT_LABELS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]


def ensure_utc_timestamp(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    return df


def standardize_wind_speed(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    factor = df["source"].map(WIND_SPEED_TO_MS).fillna(1.0)
    df["wind_speed"] = df["wind_speed"] * factor
    return df


def _octant(direction: float | None) -> str | None:
    if direction is None or pd.isna(direction):
        return None
    index = int(((direction % 360) + 22.5) // 45) % 8
    return OCTANT_LABELS[index]


def classify_wind_direction_octant(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["wind_direction_octant"] = df["wind_direction"].apply(_octant)
    return df


def transform(df: pd.DataFrame) -> pd.DataFrame:
    df = ensure_utc_timestamp(df)
    df = standardize_wind_speed(df)
    df = classify_wind_direction_octant(df)
    return df
