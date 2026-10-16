"""FastAPI application: routes for the task API and the health check."""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Path, Request, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import Session

from . import cache
from .config import settings
from .database import engine, get_db, init_db
from .models import Task
from .schemas import TaskCreate, TaskRead, TaskUpdate

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("tasks.api")

# Task ids are 32-bit integers in PostgreSQL; this rejects absurd ids with a 422
# instead of letting them reach the database.
TaskId = Annotated[int, Path(ge=1, le=2_147_483_647, description="The task's numeric id")]


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Task Management API")
    init_db()  # create tables if needed (blocking is fine during startup)
    yield
    engine.dispose()
    logger.info("Task Management API stopped")


app = FastAPI(
    title="Task Management API",
    description="A small REST API backed by PostgreSQL, with Redis caching for the task list.",
    version="1.0.0",
    lifespan=lifespan,  # interactive docs are served at /docs and /redoc
)


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    """Turn unexpected database failures into clean JSON instead of a stack trace."""
    logger.error("Database error on %s %s", request.method, request.url.path, exc_info=exc)
    if isinstance(exc, OperationalError):
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "Database unavailable. Try again shortly."},
        )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal database error."},
    )


def check_database() -> bool:
    """Return True if a trivial query succeeds."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as exc:
        logger.warning("Health check: database is down (%s)", exc.__class__.__name__)
        return False


@app.get("/health", tags=["health"])
def health(response: Response):
    """Liveness and dependency check.

    Returns 200 when PostgreSQL answers, 503 when it does not. Redis being
    down does not make the API unhealthy, because the API works without it.
    """
    database_up = check_database()
    if not database_up:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ok" if database_up else "unavailable",
        "database": "up" if database_up else "down",
        "redis": cache.ping(),
    }


@app.get("/api/tasks", response_model=list[TaskRead], tags=["tasks"])
def list_tasks(response: Response, db: Session = Depends(get_db)):
    """List all tasks, newest first. Served from Redis when a cached copy exists.

    The X-Cache response header says whether the cache was used (HIT) or not (MISS).
    """
    cached = cache.get_cached_tasks()
    if cached is not None:
        response.headers["X-Cache"] = "HIT"
        return cached

    tasks = db.scalars(select(Task).order_by(Task.created_at.desc(), Task.id.desc())).all()
    payload = [TaskRead.model_validate(task).model_dump(mode="json") for task in tasks]
    cache.set_cached_tasks(payload)
    response.headers["X-Cache"] = "MISS"
    return payload


@app.get("/api/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
def get_task(task_id: TaskId, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@app.post(
    "/api/tasks",
    response_model=TaskRead,
    status_code=status.HTTP_201_CREATED,
    tags=["tasks"],
)
def create_task(payload: TaskCreate, db: Session = Depends(get_db)):
    task = Task(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    cache.invalidate_tasks_cache()  # only after the data is safely committed
    logger.info("Created task id=%s", task.id)
    return task


@app.put("/api/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
def update_task(task_id: TaskId, payload: TaskUpdate, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    for field, value in payload.model_dump().items():
        setattr(task, field, value)
    db.commit()
    db.refresh(task)
    cache.invalidate_tasks_cache()
    logger.info("Updated task id=%s", task.id)
    return task


@app.delete("/api/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tasks"])
def delete_task(task_id: TaskId, db: Session = Depends(get_db)):
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    db.delete(task)
    db.commit()
    cache.invalidate_tasks_cache()
    logger.info("Deleted task id=%s", task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
