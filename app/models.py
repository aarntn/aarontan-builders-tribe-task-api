from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Column, DateTime, String, Text

from app.database import Base


def new_task_id():
    return str(uuid4())


def utc_now():
    return datetime.now(UTC)


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=new_task_id)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
    idempotency_key = Column(String(255), nullable=False, unique=True)
    request_fingerprint = Column(String(64), nullable=False)
