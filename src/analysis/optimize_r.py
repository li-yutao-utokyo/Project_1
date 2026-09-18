from __future__ import annotations

import numpy as np
import pandas as pd

from src.analysis.wind_comfort import (
    DEFAULT_STRONG_WIND_THRESHOLD,
    DEFAULT_WEAK_WIND_THRESHOLD,
    classify_uncomfortable_days,
)


def optimize_r(
    df: pd.DataFrame,
    *,
    r_min: float = 0.3,
    r_max: float = 1.0,
    r_step: float = 0.01,
    strong_threshold: float = DEFAULT_STRONG_WIND_THRESHOLD,
    weak_threshold: float = DEFAULT_WEAK_WIND_THRESHOLD,
) -> pd.DataFrame:
    """Grid-search R over [r_min, r_max] and count uncomfortable days at each step.

    Returns a DataFrame with columns: r, strong_wind_days, weak_wind_days,
    total_days — ready for a Dashboard to plot "uncomfortable days vs R".
    """
    r_values = np.round(np.arange(r_min, r_max + r_step / 2, r_step), 10)

    rows = []
    for r in r_values:
        daily = classify_uncomfortable_days(
            df, float(r), strong_threshold=strong_threshold, weak_threshold=weak_threshold
        )
        strong_days = int(daily["strong_wind_day"].sum())
        weak_days = int(daily["weak_wind_day"].sum())
        rows.append(
            {
                "r": round(float(r), 2),
                "strong_wind_days": strong_days,
                "weak_wind_days": weak_days,
                "total_days": strong_days + weak_days,
            }
        )
    return pd.DataFrame(rows)


def find_optimal_r(result: pd.DataFrame) -> pd.Series:
    """Return the row with the minimum total_days, breaking ties on the smallest R."""
    best_total = result["total_days"].min()
    candidates = result[result["total_days"] == best_total]
    return candidates.iloc[0]
