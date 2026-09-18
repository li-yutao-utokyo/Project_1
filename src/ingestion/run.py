from __future__ import annotations

import argparse
import datetime
from collections.abc import Sequence

from sqlalchemy import Engine

from src.ingestion.openmeteo_client import fetch_historical_weather, parse_openmeteo_response
from src.storage.db import get_session
from src.storage.models import RawObservation


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch historical weather observations from Open-Meteo and "
        "store them as raw_observations."
    )
    parser.add_argument("--city", required=True, help="e.g. tokyo, osaka, nagoya")
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
    """Fetch, parse, and persist observations for `city`. Returns the row count."""
    payload = fetch_historical_weather(city, start, end)
    records = parse_openmeteo_response(payload, city=city)

    with get_session(engine=engine) as session:
        session.add_all(RawObservation(**record) for record in records)
        session.commit()

    return len(records)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    count = run(args.city, args.start, args.end)
    print(f"Inserted {count} raw observations for {args.city} ({args.start} ~ {args.end}).")


if __name__ == "__main__":
    main()
