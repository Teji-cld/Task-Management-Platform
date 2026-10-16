"""Redis caching for GET /api/tasks.

Every function here is safe to call when Redis is down or disabled: failures are
logged and the caller simply behaves as if the cache were empty. The API then
reads from PostgreSQL, so Redis is an optimisation, never a requirement.
"""

import json
import logging
from typing import Any, Optional

import redis

from .config import settings

logger = logging.getLogger("tasks.cache")

TASKS_LIST_KEY = "tasks:list"

_client: Optional[redis.Redis] = None


def get_client() -> Optional[redis.Redis]:
    """Return the shared Redis client, or None when caching is disabled.

    Creating the client does not connect; the first command does. Short
    timeouts stop a dead Redis from making every request slow.
    """
    global _client
    if not settings.redis_enabled:
        return None
    if _client is None:
        _client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password,
            socket_connect_timeout=settings.redis_socket_timeout,
            socket_timeout=settings.redis_socket_timeout,
            decode_responses=True,
        )
    return _client


def get_cached_tasks() -> Optional[list[dict[str, Any]]]:
    """Return the cached task list, or None on a miss or any Redis problem."""
    client = get_client()
    if client is None:
        return None
    try:
        raw = client.get(TASKS_LIST_KEY)
    except redis.exceptions.RedisError as exc:
        logger.warning("Redis read failed, using the database instead: %s", exc)
        return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        logger.warning("Cached value was not valid JSON; ignoring it")
        return None


def set_cached_tasks(tasks: list[dict[str, Any]]) -> None:
    """Store the task list; it expires after CACHE_TTL_SECONDS."""
    client = get_client()
    if client is None:
        return
    try:
        client.setex(TASKS_LIST_KEY, settings.cache_ttl_seconds, json.dumps(tasks))
    except redis.exceptions.RedisError as exc:
        logger.warning("Redis write failed, response was not cached: %s", exc)


def invalidate_tasks_cache() -> None:
    """Delete the cached list so the next GET reads fresh data.

    If Redis is down, the old entry can survive until it expires (at most
    CACHE_TTL_SECONDS), which is why the TTL exists.
    """
    client = get_client()
    if client is None:
        return
    try:
        client.delete(TASKS_LIST_KEY)
    except redis.exceptions.RedisError as exc:
        logger.warning("Redis invalidate failed, cache may be stale until it expires: %s", exc)


def ping() -> str:
    """Report Redis status for /health: 'up', 'down' or 'disabled'."""
    client = get_client()
    if client is None:
        return "disabled"
    try:
        client.ping()
        return "up"
    except redis.exceptions.RedisError:
        return "down"
