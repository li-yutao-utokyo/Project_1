from __future__ import annotations

import pandas as pd

from src.processing.transform import OCTANT_LABELS

# Pedestrian-height wind comfort thresholds (m/s). Simplified stand-ins for a
# full Lawson-criteria-style probability-of-exceedance analysis (see README §8):
# a day counts as uncomfortable if its representative (daily max) pedestrian
# wind speed crosses either bound.
DEFAULT_STRONG_WIND_THRESHOLD = 5.0
DEFAULT_WEAK_WIND_THRESHOLD = 1.0


def pedestrian_wind_speed(df: pd.DataFrame, r: float) -> pd.DataFrame:
    """Add a pedestrian_wind_speed column: R × observed wind_speed."""
    df = df.copy()
    df["pedestrian_wind_speed"] = df["wind_speed"] * r
    return df


def daily_max_pedestrian_wind_speed(df: pd.DataFrame) -> pd.Series:
    """Daily max pedestrian_wind_speed, indexed by date."""
    day = pd.to_datetime(df["timestamp"], utc=True).dt.date
    return df["pedestrian_wind_speed"].groupby(day).max()


def classify_uncomfortable_days(
    df: pd.DataFrame,
    r: float,
    *,
    strong_threshold: float = DEFAULT_STRONG_WIND_THRESHOLD,
    weak_threshold: float = DEFAULT_WEAK_WIND_THRESHOLD,
) -> pd.DataFrame:
    """Per-day strong/weak wind comfort classification for a given R."""
    daily_max = daily_max_pedestrian_wind_speed(pedestrian_wind_speed(df, r))
    return pd.DataFrame(
        {
            "daily_max_wind_speed": daily_max,
            "strong_wind_day": daily_max > strong_threshold,
            "weak_wind_day": daily_max < weak_threshold,
        }
    )


def wind_direction_temperature_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Temperature mean/std/count grouped by wind_direction_octant."""
    return (
        df.dropna(subset=["wind_direction_octant"])
        .groupby("wind_direction_octant")["temperature"]
        .agg(["mean", "std", "count"])
        .reindex(OCTANT_LABELS)
    )
