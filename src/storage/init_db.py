from __future__ import annotations

from src.storage.db import get_engine
from src.storage.models import Base


def main() -> None:
    Base.metadata.create_all(get_engine())
    print("Database tables created (or already up to date).")


if __name__ == "__main__":
    main()
