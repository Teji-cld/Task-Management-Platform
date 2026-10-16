"""Cache behaviour, tested with in-memory fakes. No Redis server is needed."""

import pytest
import redis

from app import cache
from app.config import settings


class FakeRedis:
    """Just enough of the Redis client for the cache module."""

    def __init__(self):
        self.store = {}
        self.ttls = {}

    def get(self, key):
        return self.store.get(key)

    def setex(self, key, ttl, value):
        self.store[key] = value
        self.ttls[key] = ttl

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)

    def ping(self):
        return True


class BrokenRedis:
    """Every command fails, like a Redis server that is down."""

    def _fail(self, *args, **kwargs):
        raise redis.exceptions.ConnectionError("simulated outage")

    get = setex = delete = ping = _fail


@pytest.fixture
def fake_redis(monkeypatch):
    fake = FakeRedis()
    monkeypatch.setattr(cache, "get_client", lambda: fake)
    return fake


def test_second_list_request_is_served_from_cache(client, fake_redis, make_task):
    make_task("cache me")

    first = client.get("/api/tasks")
    second = client.get("/api/tasks")

    assert first.headers["X-Cache"] == "MISS"
    assert second.headers["X-Cache"] == "HIT"
    assert second.json() == first.json()
    assert cache.TASKS_LIST_KEY in fake_redis.store


def test_cache_entry_uses_the_configured_ttl(client, fake_redis):
    client.get("/api/tasks")

    assert fake_redis.ttls[cache.TASKS_LIST_KEY] == settings.cache_ttl_seconds


def test_creating_a_task_invalidates_the_cache(client, fake_redis):
    client.get("/api/tasks")
    assert client.get("/api/tasks").headers["X-Cache"] == "HIT"

    client.post("/api/tasks", json={"title": "fresh"})

    after = client.get("/api/tasks")
    assert after.headers["X-Cache"] == "MISS"
    assert [t["title"] for t in after.json()] == ["fresh"]


def test_updating_a_task_invalidates_the_cache(client, fake_redis, make_task):
    task = make_task("before")
    client.get("/api/tasks")  # fills the cache

    client.put(f"/api/tasks/{task['id']}", json={"title": "after", "completed": True})

    after = client.get("/api/tasks")
    assert after.headers["X-Cache"] == "MISS"
    assert after.json()[0]["title"] == "after"


def test_deleting_a_task_invalidates_the_cache(client, fake_redis, make_task):
    task = make_task("doomed")
    client.get("/api/tasks")  # fills the cache

    client.delete(f"/api/tasks/{task['id']}")

    after = client.get("/api/tasks")
    assert after.headers["X-Cache"] == "MISS"
    assert after.json() == []


def test_api_keeps_working_when_redis_is_down(client, monkeypatch):
    monkeypatch.setattr(cache, "get_client", lambda: BrokenRedis())

    created = client.post("/api/tasks", json={"title": "still works"})
    listing = client.get("/api/tasks")
    updated = client.put(
        f"/api/tasks/{created.json()['id']}", json={"title": "edited", "completed": True}
    )
    deleted = client.delete(f"/api/tasks/{created.json()['id']}")

    assert created.status_code == 201
    assert listing.status_code == 200
    assert listing.json()[0]["title"] == "still works"
    assert listing.headers["X-Cache"] == "MISS"
    assert updated.status_code == 200
    assert deleted.status_code == 204


def test_health_reports_redis_down_but_stays_200(client, monkeypatch):
    monkeypatch.setattr(cache, "get_client", lambda: BrokenRedis())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["redis"] == "down"
    assert response.json()["database"] == "up"


def test_corrupt_cache_value_is_ignored(client, fake_redis, make_task):
    make_task("real data")
    fake_redis.store[cache.TASKS_LIST_KEY] = "{not valid json"

    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.headers["X-Cache"] == "MISS"
    assert response.json()[0]["title"] == "real data"
