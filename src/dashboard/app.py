from __future__ import annotations

import datetime

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import streamlit as st
from matplotlib.figure import Figure

from src.analysis.optimize_r import find_optimal_r, optimize_r
from src.analysis.wind_comfort import (
    DEFAULT_STRONG_WIND_THRESHOLD,
    DEFAULT_WEAK_WIND_THRESHOLD,
    wind_direction_temperature_stats,
)
from src.ingestion.openmeteo_client import CITY_COORDINATES
from src.processing.transform import OCTANT_LABELS
from src.storage.db import get_session
from src.storage.models import ProcessedObservation
from src.storage.queries import load_observations

PROCESSED_COLUMNS = ["timestamp", "wind_speed", "wind_direction_octant", "temperature"]


def load_processed_observations(
    city: str, start: datetime.date, end: datetime.date
) -> pd.DataFrame:
    with get_session() as session:
        return load_observations(session, ProcessedObservation, city, start, end, PROCESSED_COLUMNS)


def wind_direction_counts(df: pd.DataFrame) -> pd.Series:
    """Observation count per octant, reindexed to a fixed N..NW order with 0 for
    octants absent from the sample (rather than being dropped by value_counts)."""
    return df["wind_direction_octant"].value_counts().reindex(OCTANT_LABELS, fill_value=0)


def render_wind_rose(counts: pd.Series) -> Figure:
    angles = np.linspace(0, 2 * np.pi, len(OCTANT_LABELS), endpoint=False)
    fig = plt.figure(figsize=(4.5, 4.5))
    ax = fig.add_subplot(projection="polar")
    ax.bar(angles, counts.values, width=2 * np.pi / len(OCTANT_LABELS) * 0.9)
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks(angles)
    ax.set_xticklabels(OCTANT_LABELS)
    ax.set_title("Wind direction frequency")
    fig.tight_layout()
    return fig


def render_scatter(df: pd.DataFrame) -> Figure:
    fig, ax = plt.subplots(figsize=(5, 4.5))
    ax.scatter(df["wind_speed"], df["temperature"], alpha=0.35, s=10)
    ax.set_xlabel("Wind speed (m/s)")
    ax.set_ylabel("Temperature (degC)")
    ax.set_title("Temperature vs wind speed")
    fig.tight_layout()
    return fig


def render_r_curve(curve: pd.DataFrame) -> Figure:
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(curve["r"], curve["total_days"], marker="o", label="total uncomfortable")
    ax.plot(curve["r"], curve["strong_wind_days"], linestyle="--", label="strong wind days")
    ax.plot(curve["r"], curve["weak_wind_days"], linestyle="--", label="weak wind days")
    ax.set_xlabel("R (pedestrian wind speed ratio)")
    ax.set_ylabel("days")
    ax.set_title("Uncomfortable days vs R")
    ax.legend()
    fig.tight_layout()
    return fig


def main() -> None:
    st.set_page_config(page_title="Urban Climate ETL Dashboard", layout="wide")
    st.title("城市気候データ ETL — 分析ダッシュボード")

    with st.sidebar:
        st.header("Data selection")
        cities = sorted(CITY_COORDINATES)
        default_city_index = cities.index("tokyo") if "tokyo" in cities else 0
        city = st.selectbox("City", cities, index=default_city_index)
        default_end = datetime.date.today() - datetime.timedelta(days=1)
        default_start = default_end - datetime.timedelta(days=89)
        start = st.date_input("Start date", default_start)
        end = st.date_input("End date", default_end)

        st.header("R optimization")
        r_min, r_max = st.slider("R range", 0.1, 2.0, (0.3, 1.0), step=0.05)
        r_step = st.select_slider("R step", options=[0.01, 0.02, 0.05, 0.1], value=0.01)
        strong_threshold = st.number_input(
            "Strong wind threshold (m/s)", value=DEFAULT_STRONG_WIND_THRESHOLD
        )
        weak_threshold = st.number_input(
            "Weak wind threshold (m/s)", value=DEFAULT_WEAK_WIND_THRESHOLD
        )

    if start > end:
        st.error("Start date must not be after end date.")
        return

    df = load_processed_observations(city, start, end)
    if df.empty:
        st.warning(
            f"No processed observations for **{city}** between {start} and {end}. "
            "Run `python -m src.ingestion.run` and `python -m src.processing.run` for "
            "this range first."
        )
        return

    st.caption(f"{len(df)} hourly observations, {city}, {start} ~ {end}")

    col1, col2 = st.columns(2)
    with col1:
        st.pyplot(render_wind_rose(wind_direction_counts(df)))
    with col2:
        st.pyplot(render_scatter(df))

    st.subheader("Wind direction vs temperature")
    st.dataframe(wind_direction_temperature_stats(df))

    st.subheader("Pedestrian wind comfort: R grid search")
    curve = optimize_r(
        df,
        r_min=r_min,
        r_max=r_max,
        r_step=r_step,
        strong_threshold=strong_threshold,
        weak_threshold=weak_threshold,
    )
    optimal = find_optimal_r(curve)
    st.pyplot(render_r_curve(curve))
    st.metric(
        "Optimal R",
        f"{optimal['r']:.2f}",
        help=(
            f"strong={optimal['strong_wind_days']:.0f}, weak={optimal['weak_wind_days']:.0f}, "
            f"total={optimal['total_days']:.0f} uncomfortable days"
        ),
    )


if __name__ == "__main__":
    main()
