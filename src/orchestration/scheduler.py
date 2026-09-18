from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Sequence

from apscheduler.schedulers.blocking import BlockingScheduler

from src.orchestration.pipeline import run_daily_pipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

DEFAULT_CITIES = ["tokyo"]


def cities_from_env() -> list[str]:
    raw = os.environ.get("PIPELINE_CITIES", ",".join(DEFAULT_CITIES))
    return [c.strip() for c in raw.split(",") if c.strip()]


def run_all_cities(cities: list[str] | None = None) -> None:
    for city in cities or cities_from_env():
        try:
            run_daily_pipeline(city)
        except Exception:
            logger.exception("daily pipeline failed for city=%s", city)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MVP scheduler for the daily ETL pipeline (APScheduler). "
        "Superseded by the Airflow DAG in orchestration/dags/ for the advanced setup."
    )
    parser.add_argument(
        "--once", action="store_true", help="Run the pipeline immediately once, then exit."
    )
    parser.add_argument(
        "--hour", type=int, default=1, help="UTC hour to run at daily when not --once (default 1)."
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)

    if args.once:
        run_all_cities()
        return

    scheduler = BlockingScheduler(timezone="UTC")
    scheduler.add_job(run_all_cities, "cron", hour=args.hour, minute=0, id="daily_pipeline")
    logger.info("Scheduler started; daily pipeline will run at %02d:00 UTC.", args.hour)
    scheduler.start()


if __name__ == "__main__":
    main()
