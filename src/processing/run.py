from __future__ import annotations

import argparse
import datetime
from collections.abc import Sequence

from sqlalchemy import Engine, delete

from src.processing.clean import clean
from src.processing.transform import transform
from src.storage.db import get_session
from src.storage.models import ProcessedObservation, RawObservation
from src.storage.queries import day_bounds, load_observations

RAW_COLUMNS = [
    "city",
    "timestamp",
    "wind_speed",
    "wind_direction",
    "temperature",
    "humidity",
    "source",
]


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean and transform raw_observations into processed_observations "
        "for a city/date range."
    )
    parser.add_argument("--city", required=True)
    parser.add_argument("--start", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--end", required=True, type=datetime.date.fromisoformat)
    return parser.parse_args(argv)


def run(
    city: str,
    start: datetime.date,
    end: datetime.date,
    *,
    engine: Engine | None = None,
) -> int:
    """Clean+transform raw_observations for `city`/[start, end] and (re)write
    the matching processed_observations rows. Returns the row count written."""
    with get_session(engine=engine) as session:
        raw_df = load_observations(session, RawObservation, city, start, end, RAW_COLUMNS)
        if raw_df.empty:
            return 0

        processed_df = transform(clean(raw_df))

        start_dt, end_dt = day_bounds(start, end)
        session.execute(
            delete(ProcessedObservation).where(
                ProcessedObservation.city == city,
                ProcessedObservation.timestamp >= start_dt,
                ProcessedObservation.timestamp <= end_dt,
            )
        )
        session.add_all(
            ProcessedObservation(
                city=row.city,
                timestamp=row.timestamp.to_pydatetime(),
                wind_speed=row.wind_speed,
                wind_direction=row.wind_direction,
                wind_direction_octant=row.wind_direction_octant,
                temperature=row.temperature,
                humidity=row.humidity,
                source=row.source,
            )
            for row in processed_df.itertuples()
        )
        session.commit()
        return len(processed_df)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    count = run(args.city, args.start, args.end)
    print(f"Wrote {count} processed observations for {args.city} ({args.start} ~ {args.end}).")


if __name__ == "__main__":
    main()
