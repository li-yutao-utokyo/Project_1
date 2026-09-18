from __future__ import annotations

import datetime

from airflow import DAG
from airflow.operators.python import PythonOperator

from src.analysis.run import run as run_analysis
from src.ingestion.run import run as run_ingestion
from src.orchestration.pipeline import DEFAULT_ANALYSIS_WINDOW_DAYS
from src.processing.run import run as run_processing

# Advanced orchestration stage (README §7 Phase 4). Mirrors
# orchestration/pipeline.run_daily_pipeline as three separate tasks per city
# instead of one function call, so ingestion/processing/analysis show up as
# distinct, independently retryable/observable steps in the Airflow UI.
CITIES = ["tokyo"]


def _target_date(**context) -> datetime.date:
    # logical_date (not data_interval_start) so a manually-triggered run's
    # --logical-date controls which day gets processed; for a scheduled daily
    # cron run the two coincide anyway.
    return context["logical_date"].date()


def ingest_task(city: str, **context) -> None:
    date = _target_date(**context)
    count = run_ingestion(city, date, date)
    print(f"ingested {count} raw rows for {city} on {date}")


def process_task(city: str, **context) -> None:
    date = _target_date(**context)
    count = run_processing(city, date, date)
    print(f"processed {count} rows for {city} on {date}")


def analyze_task(city: str, **context) -> None:
    date = _target_date(**context)
    window_start = date - datetime.timedelta(days=DEFAULT_ANALYSIS_WINDOW_DAYS - 1)
    optimal, _curve = run_analysis(city, window_start, date)
    if optimal is not None:
        print(f"optimal R={optimal['r']:.2f} total_uncomfortable_days={optimal['total_days']}")
    else:
        print(f"no processed observations for {city} in {window_start}~{date}")


with DAG(
    dag_id="daily_pipeline",
    description="Ingest -> process -> analyze one day of weather data, per city.",
    schedule="0 1 * * *",
    start_date=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    catchup=False,
    tags=["urban-climate-etl"],
) as dag:
    for city in CITIES:
        ingest = PythonOperator(
            task_id=f"ingest_{city}",
            python_callable=ingest_task,
            op_kwargs={"city": city},
        )
        process = PythonOperator(
            task_id=f"process_{city}",
            python_callable=process_task,
            op_kwargs={"city": city},
        )
        analyze = PythonOperator(
            task_id=f"analyze_{city}",
            python_callable=analyze_task,
            op_kwargs={"city": city},
        )
        ingest >> process >> analyze
