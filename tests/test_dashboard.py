from __future__ import annotations

import datetime

import pandas as pd
from matplotlib.figure import Figure

from src.dashboard.app import (
    render_r_curve,
    render_scatter,
    render_wind_rose,
    wind_direction_counts,
)
from src.processing.transform import OCTANT_LABELS


def _df(octants: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [
                datetime.datetime(2024, 6, 1, h, tzinfo=datetime.UTC) for h in range(len(octants))
            ],
            "wind_speed": [2.0] * len(octants),
            "wind_direction_octant": octants,
            "temperature": [20.0] * len(octants),
        }
    )


def test_wind_direction_counts_reindexes_to_fixed_order_with_zero_fill():
    counts = wind_direction_counts(_df(["N", "N", "E"]))
    assert list(counts.index) == OCTANT_LABELS
    assert counts["N"] == 2
    assert counts["E"] == 1
    assert counts["S"] == 0


def test_render_wind_rose_returns_a_figure():
    counts = wind_direction_counts(_df(["N", "NE", "E"]))
    fig = render_wind_rose(counts)
    assert isinstance(fig, Figure)


def test_render_scatter_returns_a_figure():
    fig = render_scatter(_df(["N", "S", "E"]))
    assert isinstance(fig, Figure)


def test_render_r_curve_returns_a_figure():
    curve = pd.DataFrame(
        {
            "r": [0.3, 0.4, 0.5],
            "strong_wind_days": [2, 1, 0],
            "weak_wind_days": [0, 0, 1],
            "total_days": [2, 1, 1],
        }
    )
    fig = render_r_curve(curve)
    assert isinstance(fig, Figure)
