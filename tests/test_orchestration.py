from __future__ import annotations

import datetime

import pandas as pd
import pytest

from src.orchestration import pipeline as pipeline_module
from src.orchestration import scheduler as scheduler_module
from src.orchestration.pipeline import run_daily_pipeline


def test_run_daily_pipeline_defaults_to_yesterday_and_chains_steps(
    monkeypatch: pytest.MonkeyPatch,
):
    calls = {}

    def fake_ingestion(city, start, end):
        calls["ingestion"] = (city, start, end)
        return 24

    def fake_processing(city, start, end):
        calls["processing"] = (city, start, end)
        return 20

    def fake_analysis(city, start, end):
        calls["analysis"] = (city, start, end)
        return {"r": 0.5, "total_days": 0}, pd.DataFrame({"r": [0.5]})

    monkeypatch.setattr(pipeline_module, "run_ingestion", fake_ingestion)
    monkeypatch.setattr(pipeline_module, "run_processing", fake_processing)
    monkeypatch.setattr(pipeline_module, "run_analysis", fake_analysis)

    today = datetime.datetime.now(datetime.UTC).date()
    yesterday = today - datetime.timedelta(days=1)

    result = run_daily_pipeline("tokyo")

    assert calls["ingestion"] == ("tokyo", yesterday, yesterday)
    assert calls["processing"] == ("tokyo", yesterday, yesterday)
    analysis_city, analysis_start, analysis_end = calls["analysis"]
    assert analysis_city == "tokyo"
    assert analysis_end == yesterday
    assert analysis_start == yesterday - datetime.timedelta(days=29)  # 30-day window
    assert result == {"ingested": 24, "processed": 20, "analysis_rows": 1}


def test_run_daily_pipeline_accepts_explicit_target_date(monkeypatch: pytest.MonkeyPatch):
    calls = {}
    monkeypatch.setattr(
        pipeline_module, "run_ingestion", lambda city, s, e: calls.setdefault("i", (s, e)) or 1
    )
    monkeypatch.setattr(
        pipeline_module, "run_processing", lambda city, s, e: calls.setdefault("p", (s, e)) or 1
    )
    monkeypatch.setattr(
        pipeline_module,
        "run_analysis",
        lambda city, s, e: (None, pd.DataFrame()),
    )

    target = datetime.date(2024, 6, 15)
    run_daily_pipeline("osaka", target, analysis_window_days=7)

    assert calls["i"] == (target, target)
    assert calls["p"] == (target, target)


def test_run_daily_pipeline_skips_log_when_no_analysis_result(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pipeline_module, "run_ingestion", lambda city, s, e: 0)
    monkeypatch.setattr(pipeline_module, "run_processing", lambda city, s, e: 0)
    monkeypatch.setattr(pipeline_module, "run_analysis", lambda city, s, e: (None, pd.DataFrame()))

    result = run_daily_pipeline("tokyo", datetime.date(2024, 6, 1))
    assert result == {"ingested": 0, "processed": 0, "analysis_rows": 0}


def test_cities_from_env_defaults_and_parses_csv(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PIPELINE_CITIES", raising=False)
    assert scheduler_module.cities_from_env() == ["tokyo"]

    monkeypatch.setenv("PIPELINE_CITIES", "tokyo, osaka ,nagoya")
    assert scheduler_module.cities_from_env() == ["tokyo", "osaka", "nagoya"]


def test_run_all_cities_continues_after_one_city_fails(monkeypatch: pytest.MonkeyPatch):
    processed_cities = []

    def fake_pipeline(city):
        if city == "osaka":
            raise RuntimeError("boom")
        processed_cities.append(city)

    monkeypatch.setattr(scheduler_module, "run_daily_pipeline", fake_pipeline)
    scheduler_module.run_all_cities(["tokyo", "osaka", "nagoya"])

    assert processed_cities == ["tokyo", "nagoya"]
