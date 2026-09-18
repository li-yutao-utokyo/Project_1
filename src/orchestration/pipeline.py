from __future__ import annotations

import datetime
import logging

from src.analysis.run import run as run_analysis
from src.ingestion.run import run as run_ingestion
from src.processing.run import run as run_processing

logger = logging.getLogger(__name__)

DEFAULT_ANALYSIS_WINDOW_DAYS = 30


def run_daily_pipeline(
    city: str,
    target_date: datetime.date | None = None,
    *,
    analysis_window_days: int = DEFAULT_ANALYSIS_WINDOW_DAYS,
) -> dict[str, int]:
    """Ingest + process `target_date` (default: yesterday, UTC) for `city`, then
    re-run the R optimization over the trailing `analysis_window_days` window.

    Reused by both the APScheduler MVP (orchestration/scheduler.py) and the
    Airflow DAG (orchestration/dags/daily_pipeline.py) so the two stay in sync.
    """
    target_date = target_date or (
        datetime.datetime.now(datetime.UTC).date() - datetime.timedelta(days=1)
    )

    ingested = run_ingestion(city, target_date, target_date)
    logger.info("ingested %d raw rows for %s on %s", ingested, city, target_date)

    processed = run_processing(city, target_date, target_date)
    logger.info("processed %d rows for %s on %s", processed, city, target_date)

    window_start = target_date - datetime.timedelta(days=analysis_window_days - 1)
    optimal, curve = run_analysis(city, window_start, target_date)
    if optimal is not None:
        logger.info(
            "analysis window %s~%s for %s: optimal R=%.2f, total_uncomfortable_days=%d",
            window_start,
            target_date,
            city,
            optimal["r"],
            optimal["total_days"],
        )

    return {"ingested": ingested, "processed": processed, "analysis_rows": len(curve)}
