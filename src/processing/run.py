from __future__ import annotations

import argparse
import datetime
from collections.abc import Sequence

import pandas as pd
from sqlalchemy import Engine, delete, select
from sqlalchemy.orm import Session

from src.processing.clean import clean
from src.processing.transform import transform
from src.storage.db import get_session
from src.storage.models import ProcessedObservation, RawObservation


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Clean and transform raw_observations into processed_observations "
        "for a city/date range."
    )
    parser.add_argument("--city", required=True)
    parser.add_argument("--start", required=True, type=datetime.date.fromisoformat)
    parser.add_argument("--end", required=True, type=datetime.date.fromisoformat)
    return parser.parse_args(argv)


def _day_bounds(
    start: datetime.date, end: datetime.date
) -> tuple[datetime.datetime, datetime.datetime]:
    start_dt = datetime.datetime.combine(start, datetime.time.min, tzinfo=datetime.UTC)
    end_dt = datetime.datetime.combine(end, datetime.time.max, tzinfo=datetime.UTC)
    return start_dt, end_dt


def _load_raw(
    session: Session, city: str, start: datetime.date, end: datetime.date
) -> pd.DataFrame:
    start_dt, end_dt = _day_bounds(start, end)
    stmt = select(RawObservation).where(
        RawObservation.city == city,
        RawObservation.timestamp >= start_dt,
        RawObservation.timestamp <= end_dt,
    )
    rows = session.execute(stmt).scalars().all()
    return pd.DataFrame(
        [
            {
                "city": r.city,
                "timestamp": r.timestamp,
                "wind_speed": r.wind_speed,
                "wind_direction": r.wind_direction,
                "temperature": r.temperature,
                "humidity": r.humidity,
                "source": r.source,
            }
            for r in rows
        ]
    )


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
        raw_df = _load_raw(session, city, start, end)
        if raw_df.empty:
            return 0

        processed_df = transform(clean(raw_df))

        start_dt, end_dt = _day_bounds(start, end)
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
