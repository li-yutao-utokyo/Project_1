from __future__ import annotations

import os
from collections.abc import Generator
from contextlib import contextmanager

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

_engine: Engine | None = None


def get_database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and configure it.")
    return url


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(get_database_url(), future=True)
    return _engine


@contextmanager
def get_session(engine: Engine | None = None) -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session. Pass `engine` explicitly (e.g. an in-memory
    SQLite engine) to override the default DATABASE_URL-backed engine in tests."""
    session_factory = sessionmaker(bind=engine or get_engine(), expire_on_commit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
