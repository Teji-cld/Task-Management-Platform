"""Request and response shapes (Pydantic). FastAPI uses these to validate input
and to build the interactive documentation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TaskBase(BaseModel):
    # Leading/trailing spaces are removed before length rules are checked,
    # so a title of "   " is rejected as empty.
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)

    @field_validator("description")
    @classmethod
    def blank_description_becomes_none(cls, value: Optional[str]) -> Optional[str]:
        return value or None


class TaskCreate(TaskBase):
    """Body of POST /api/tasks."""

    completed: bool = False


class TaskUpdate(TaskBase):
    """Body of PUT /api/tasks/{id}. PUT replaces the whole task, so every
    field must be sent (completed is required so it is never reset by accident)."""

    completed: bool


class TaskRead(BaseModel):
    """What the API returns for a task."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: Optional[str]
    completed: bool
    created_at: datetime
    updated_at: datetime
