from __future__ import annotations

import argparse
import datetime
from collections.abc import Sequence

from sqlalchemy import Engine, delete

from src.analysis.optimize_r import find_optimal_r, optimize_r
from src.analysis.wind_comfort import (
    DEFAULT_STRONG_WIND_THRESHOLD,
    DEFAULT_WEAK_WIND_THRESHOLD,
    wind_direction_temperature_stats,
)
from src.storage.db import get_session
from src.storage.models import ProcessedObservation, RWindOptimizationResult
from src.storage.queries import load_observations

PROCESSED_COLUMNS = ["timestamp", "wind_speed", "wind_direction_octant", "temperature"]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run wind-direction/temperature stats and the R grid search over "
        "processed_observations for a city/date range."
    )
    parser.add_argument("--city", required=True)
    parser.add_argument("--start", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--end", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--r-min", type=float, default=0.3)
    parser.add_argument("--r-max", type=float, default=1.0)
    parser.add_argument("--r-step", type=float, default=0.01)
    parser.add_argument("--strong-threshold", type=float, default=DEFAULT_STRONG_WIND_THRESHOLD)
    parser.add_argument("--weak-threshold", type=float, default=DEFAULT_WEAK_WIND_THRESHOLD)
    parser.add_argument(
        "--plot",
        metavar="PATH",
        help="Save an 'uncomfortable days vs R' PNG to PATH (requires matplotlib).",
    )
    return parser.parse_args(argv)


def run(
    city: str,
    start: datetime.date,
    end: datetime.date,
    *,
    r_min: float = 0.3,
    r_max: float = 1.0,
    r_step: float = 0.01,
    strong_threshold: float = DEFAULT_STRONG_WIND_THRESHOLD,
    weak_threshold: float = DEFAULT_WEAK_WIND_THRESHOLD,
    engine: Engine | None = None,
) -> tuple[object | None, object]:
    """Run the R grid search for `city`/[start, end], persist the curve to
    analysis_r_optimization, and return (optimal_r_row, curve_df).

    optimal_r_row is None when there is no processed data for the range."""
    with get_session(engine=engine) as session:
        df = load_observations(session, ProcessedObservation, city, start, end, PROCESSED_COLUMNS)
        if df.empty:
            return None, df

        curve = optimize_r(
            df,
            r_min=r_min,
            r_max=r_max,
            r_step=r_step,
            strong_threshold=strong_threshold,
            weak_threshold=weak_threshold,
        )
        optimal = find_optimal_r(curve)

        session.execute(
            delete(RWindOptimizationResult).where(
                RWindOptimizationResult.city == city,
                RWindOptimizationResult.period_start == start,
                RWindOptimizationResult.period_end == end,
            )
        )
        session.add_all(
            RWindOptimizationResult(
                city=city,
                r_value=row.r,
                strong_wind_days=row.strong_wind_days,
                weak_wind_days=row.weak_wind_days,
                total_uncomfortable_days=row.total_days,
                period_start=start,
                period_end=end,
            )
            for row in curve.itertuples()
        )
        session.commit()

        return optimal, curve


def _save_plot(curve, path: str) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(curve["r"], curve["total_days"], marker="o", label="total uncomfortable days")
    ax.plot(curve["r"], curve["strong_wind_days"], linestyle="--", label="strong wind days")
    ax.plot(curve["r"], curve["weak_wind_days"], linestyle="--", label="weak wind days")
    ax.set_xlabel("R (pedestrian wind speed ratio)")
    ax.set_ylabel("days")
    ax.set_title("Uncomfortable days vs R")
    ax.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    optimal, curve = run(
        args.city,
        args.start,
        args.end,
        r_min=args.r_min,
        r_max=args.r_max,
        r_step=args.r_step,
        strong_threshold=args.strong_threshold,
        weak_threshold=args.weak_threshold,
    )

    if optimal is None:
        print(f"No processed observations for {args.city} ({args.start} ~ {args.end}).")
        return

    with get_session() as session:
        df = load_observations(
            session, ProcessedObservation, args.city, args.start, args.end, PROCESSED_COLUMNS
        )
    stats = wind_direction_temperature_stats(df)

    print(f"Wind direction vs temperature ({args.city}, {args.start} ~ {args.end}):")
    print(stats.to_string())
    print()
    print(
        f"Optimal R = {optimal['r']:.2f} -> strong={optimal['strong_wind_days']}, "
        f"weak={optimal['weak_wind_days']}, total={optimal['total_days']} uncomfortable days"
    )

    if args.plot:
        _save_plot(curve, args.plot)
        print(f"Saved plot to {args.plot}")


if __name__ == "__main__":
    main()
