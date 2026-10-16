"""Tests that need REAL PostgreSQL and Redis servers.

They are skipped unless you run with TEST_USE_EXTERNAL_SERVICES=1 (see README).
"""

import os

import pytest

from app.database import engine

pytestmark = pytest.mark.skipif(
    os.environ.get("TEST_USE_EXTERNAL_SERVICES") != "1",
    reason="needs real PostgreSQL and Redis; set TEST_USE_EXTERNAL_SERVICES=1 to run",
)


def test_database_is_postgresql():
    assert engine.dialect.name == "postgresql"


def test_health_reports_postgres_and_redis_up(client):
    body = client.get("/health").json()

    assert body["database"] == "up"
    assert body["redis"] == "up"


def test_real_redis_caches_the_task_list(client, make_task):
    make_task("cached in real redis")

    first = client.get("/api/tasks")
    second = client.get("/api/tasks")

    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
