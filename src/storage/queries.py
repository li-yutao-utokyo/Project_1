from __future__ import annotations

import datetime
from collections.abc import Sequence
from typing import Any

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session


def day_bounds(
    start: datetime.date, end: datetime.date
) -> tuple[datetime.datetime, datetime.datetime]:
    """Turn a [start, end] date range into UTC datetime bounds covering both full days."""
    start_dt = datetime.datetime.combine(start, datetime.time.min, tzinfo=datetime.UTC)
    end_dt = datetime.datetime.combine(end, datetime.time.max, tzinfo=datetime.UTC)
    return start_dt, end_dt


def load_observations(
    session: Session,
    model: type[Any],
    city: str,
    start: datetime.date,
    end: datetime.date,
    columns: Sequence[str],
) -> pd.DataFrame:
    """Load rows of `model` for `city` within [start, end] as a DataFrame of `columns`."""
    start_dt, end_dt = day_bounds(start, end)
    stmt = select(model).where(
        model.city == city,
        model.timestamp >= start_dt,
        model.timestamp <= end_dt,
    )
    rows = session.execute(stmt).scalars().all()
    return pd.DataFrame([{col: getattr(row, col) for col in columns} for row in rows])
