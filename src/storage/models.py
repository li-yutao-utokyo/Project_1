from __future__ import annotations

import datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawObservation(Base):
    """Raw hourly weather observation as ingested from a data source (see README §9)."""

    __tablename__ = "raw_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(100), index=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    wind_speed: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_direction: Mapped[float | None] = mapped_column(Float, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50))
    ingested_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProcessedObservation(Base):
    """Cleaned/standardized observation derived from raw_observations (see README §9)."""

    __tablename__ = "processed_observations"

    id: Mapped[int] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(100), index=True)
    timestamp: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), index=True)
    wind_speed: Mapped[float] = mapped_column(Float)
    wind_direction: Mapped[float | None] = mapped_column(Float, nullable=True)
    wind_direction_octant: Mapped[str | None] = mapped_column(String(2), nullable=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float | None] = mapped_column(Float, nullable=True)
    source: Mapped[str] = mapped_column(String(50))
    processed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RWindOptimizationResult(Base):
    """One (R, uncomfortable-day-count) sample from the R grid search (see README §8-9).

    `city` is not in the README's initial sketch but is added so results from
    different cities don't collide once more than one city is analyzed.
    """

    __tablename__ = "analysis_r_optimization"

    id: Mapped[int] = mapped_column(primary_key=True)
    city: Mapped[str] = mapped_column(String(100), index=True)
    r_value: Mapped[float] = mapped_column(Float)
    strong_wind_days: Mapped[int] = mapped_column(Integer)
    weak_wind_days: Mapped[int] = mapped_column(Integer)
    total_uncomfortable_days: Mapped[int] = mapped_column(Integer)
    period_start: Mapped[datetime.date] = mapped_column(Date, index=True)
    period_end: Mapped[datetime.date] = mapped_column(Date, index=True)
    computed_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
