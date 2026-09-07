"""SQLAlchemy wiring. Supports SQLite (local dev) and PostgreSQL (Docker)."""
from __future__ import annotations

import logging
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import settings

logger = logging.getLogger(__name__)

_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}
engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(retries: int = 10, delay: float = 2.0) -> None:
    """Create tables, retrying so PostgreSQL has time to come up in Docker."""
    import app.models  # noqa: F401  (register models)

    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine)
            return
        except Exception as exc:  # pragma: no cover - depends on infra
            last_error = exc
            logger.warning("DB init attempt %d failed: %s", attempt, exc)
            time.sleep(delay)
    raise RuntimeError(f"Could not initialise database: {last_error}")