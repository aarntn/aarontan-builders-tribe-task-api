import hashlib
import json
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Task, utc_now
from app.schemas import TaskCreate, TaskResponse, TaskStatus, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])


def get_request_fingerprint(task: TaskCreate):
    payload = task.model_dump()
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload_json.encode("utf-8")).hexdigest()


def get_task_or_404(task_id: str, db: Session):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )
    return task


@router.post(
    "",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a task",
)
def create_task(
    task: TaskCreate,
    response: Response,
    idempotency_key: Annotated[str, Header(min_length=1)],
    db: Session = Depends(get_db),
):
    idempotency_key = idempotency_key.strip()
    if not idempotency_key:
        raise HTTPException(
            status_code=422,
            detail="Idempotency-Key header is required",
        )

    request_fingerprint = get_request_fingerprint(task)
    existing_task = (
        db.query(Task)
        .filter(Task.idempotency_key == idempotency_key)
        .first()
    )

    if existing_task:
        if existing_task.request_fingerprint != request_fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Idempotency key has already been used with a different request",
            )

        response.status_code = status.HTTP_200_OK
        return existing_task

    new_task = Task(
        title=task.title,
        description=task.description,
        status="pending",
        idempotency_key=idempotency_key,
        request_fingerprint=request_fingerprint,
    )

    db.add(new_task)
    db.commit()
    db.refresh(new_task)

    return new_task


@router.get(
    "",
    response_model=list[TaskResponse],
    summary="View all tasks",
)
def get_tasks(
    task_status: Annotated[TaskStatus | None, Query(alias="status")] = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    db: Session = Depends(get_db),
):
    if created_from and created_to and created_from > created_to:
        raise HTTPException(
            status_code=422,
            detail="created_from cannot be after created_to",
        )

    query = db.query(Task)

    if task_status:
        query = query.filter(Task.status == task_status.value)

    if created_from:
        query = query.filter(Task.created_at >= created_from)

    if created_to:
        query = query.filter(Task.created_at <= created_to)

    return query.order_by(Task.created_at).all()


@router.get(
    "/{task_id}",
    response_model=TaskResponse,
    summary="View a single task",
)
def get_task(task_id: str, db: Session = Depends(get_db)):
    return get_task_or_404(task_id, db)


@router.patch(
    "/{task_id}",
    response_model=TaskResponse,
    summary="Update a task",
)
def update_task(
    task_id: str,
    task_update: TaskUpdate,
    db: Session = Depends(get_db),
):
    task = get_task_or_404(task_id, db)

    if "title" in task_update.model_fields_set:
        task.title = task_update.title

    if "description" in task_update.model_fields_set:
        task.description = task_update.description

    if "status" in task_update.model_fields_set:
        task.status = task_update.status.value

    task.updated_at = utc_now()

    db.commit()
    db.refresh(task)

    return task


@router.patch(
    "/{task_id}/complete",
    response_model=TaskResponse,
    summary="Mark a task as completed",
)
def complete_task(task_id: str, db: Session = Depends(get_db)):
    task = get_task_or_404(task_id, db)

    task.status = "completed"
    task.updated_at = utc_now()

    db.commit()
    db.refresh(task)

    return task


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a task",
)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    task = get_task_or_404(task_id, db)

    db.delete(task)
    db.commit()

    return None
