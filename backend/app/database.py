"""Database engine, sessions, and table creation."""

import logging
import time
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings

logger = logging.getLogger("tasks.database")


class Base(DeclarativeBase):
    """All database models inherit from this class."""


_engine_options = {"pool_pre_ping": True}  # test a connection before using it
if settings.database_url.get_backend_name() == "sqlite":
    # SQLite is only used by the automated tests. It needs this flag because
    # FastAPI runs request handlers in a thread pool.
    _engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **_engine_options)

# expire_on_commit=False keeps objects usable after commit() (we also refresh them).
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one database session per request.

    The session is always closed. If a database error escapes the request
    handler, the open transaction is rolled back first.
    """
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError:
        db.rollback()
        raise
    finally:
        db.close()


def init_db() -> None:
    """Create the tables if they do not exist yet.

    Base.metadata.create_all() inspects the database and only creates missing
    tables, so it is safe to run on every startup. If the database is not
    reachable yet (common when containers start together), retry a few times.
    """
    from . import models  # noqa: F401  (importing registers the Task table on Base)

    safe_url = settings.database_url.render_as_string(hide_password=True)
    attempts = max(1, settings.db_connect_retries)

    for attempt in range(1, attempts + 1):
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database ready: %s", safe_url)
            return
        except OperationalError as exc:
            logger.warning(
                "Database not reachable (attempt %s of %s): %s",
                attempt,
                attempts,
                exc.__class__.__name__,
            )
            if attempt == attempts:
                logger.error("Giving up: could not connect to %s", safe_url)
                raise
            time.sleep(settings.db_connect_retry_delay)
