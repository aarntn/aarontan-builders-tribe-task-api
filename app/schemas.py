from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TaskStatus(str, Enum):
    pending = "pending"
    completed = "completed"


class TaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class TaskUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    status: TaskStatus | None = None

    @field_validator("title", mode="before")
    @classmethod
    def strip_title(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value

    @model_validator(mode="after")
    def require_editable_field(self):
        if not self.model_fields_set:
            raise ValueError("At least one editable field is required")

        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("Title cannot be null")

        if "status" in self.model_fields_set and self.status is None:
            raise ValueError("Status cannot be null")

        return self


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: str
    title: str
    description: str | None
    status: TaskStatus
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")
