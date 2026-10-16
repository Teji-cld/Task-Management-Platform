"""Shared test setup.

By default the tests need NO external services: they run the real application
against a temporary SQLite file instead of PostgreSQL, with Redis switched off
(the cache tests use a small in-memory fake instead).

Set TEST_USE_EXTERNAL_SERVICES=1 to run the same tests against the real
PostgreSQL and Redis described by your environment / backend/.env. WARNING: in
that mode the tests delete every task in that database. Use a throwaway database.
"""

import os
import tempfile

if os.environ.get("TEST_USE_EXTERNAL_SERVICES") != "1":
    # These must be set BEFORE the app is imported, because settings are read at import time.
    _tmp_dir = tempfile.mkdtemp(prefix="tasks-tests-")
    os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_dir}/test.db"
    os.environ["REDIS_ENABLED"] = "false"
    os.environ["LOG_LEVEL"] = "WARNING"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app import cache
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import Task


@pytest.fixture(autouse=True)
def clean_state():
    """Give every test an empty tasks table and an empty cache."""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        session.execute(delete(Task))
        session.commit()
    cache.invalidate_tasks_cache()


@pytest.fixture
def client():
    # Using TestClient as a context manager runs the app's startup code (init_db).
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def make_task(client):
    """Helper that creates a task through the API and returns its JSON."""

    def _make(title="Write tests", **extra):
        response = client.post("/api/tasks", json={"title": title, **extra})
        assert response.status_code == 201, response.text
        return response.json()

    return _make
