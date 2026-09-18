from __future__ import annotations

import pandas as pd

REQUIRED_COLUMNS = ["wind_speed", "temperature"]

# Generous physical plausibility bounds, not climatology-tight thresholds.
WIND_SPEED_RANGE = (0.0, 100.0)  # m/s
TEMPERATURE_RANGE = (-90.0, 60.0)  # degrees C
WIND_DIRECTION_RANGE = (0.0, 360.0)  # degrees


def drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the most recently ingested row for each (city, timestamp, source)."""
    return df.drop_duplicates(subset=["city", "timestamp", "source"], keep="last").reset_index(
        drop=True
    )


def drop_missing_required(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows missing a field the analysis stage cannot do without."""
    return df.dropna(subset=REQUIRED_COLUMNS).reset_index(drop=True)


def filter_outliers(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows with physically implausible values (e.g. negative wind speed)."""
    speed_lo, speed_hi = WIND_SPEED_RANGE
    temp_lo, temp_hi = TEMPERATURE_RANGE
    dir_lo, dir_hi = WIND_DIRECTION_RANGE

    mask = df["wind_speed"].between(speed_lo, speed_hi)
    mask &= df["temperature"].between(temp_lo, temp_hi)
    mask &= df["wind_direction"].isna() | df["wind_direction"].between(dir_lo, dir_hi)
    return df[mask].reset_index(drop=True)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = drop_duplicates(df)
    df = drop_missing_required(df)
    df = filter_outliers(df)
    return df
