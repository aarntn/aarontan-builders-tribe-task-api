from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app
from app.models import Task


@pytest.fixture
def test_app(tmp_path):
    test_database_url = f"sqlite:///{tmp_path}/test.db"
    test_engine = create_engine(
        test_database_url,
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=test_engine,
    )

    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app), TestingSessionLocal
    app.dependency_overrides.clear()


def test_create_valid_task(test_app):
    client, _ = test_app

    response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "create-valid-task"},
        json={
            "title": "  Prepare report  ",
            "description": "Prepare weekly report",
        },
    )

    assert response.status_code == 201

    data = response.json()
    assert data["id"]
    assert data["title"] == "Prepare report"
    assert data["description"] == "Prepare weekly report"
    assert data["status"] == "pending"
    assert data["createdAt"]
    assert data["updatedAt"]


def test_create_task_without_title(test_app):
    client, _ = test_app

    response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "missing-title"},
        json={"description": "No title here"},
    )

    assert response.status_code == 422


def test_create_task_with_blank_title(test_app):
    client, _ = test_app

    response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "blank-title"},
        json={"title": "   "},
    )

    assert response.status_code == 422


def test_create_task_requires_idempotency_key(test_app):
    client, _ = test_app

    response = client.post(
        "/tasks",
        json={"title": "Prepare report"},
    )

    assert response.status_code == 422


def test_repeat_post_with_same_idempotency_key_returns_existing_task(test_app):
    client, SessionLocal = test_app
    payload = {
        "title": "Prepare report",
        "description": "Prepare weekly report",
    }

    first_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "repeat-key"},
        json=payload,
    )
    second_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "repeat-key"},
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert second_response.json()["id"] == first_response.json()["id"]

    db = SessionLocal()
    try:
        task_count = db.query(Task).count()
    finally:
        db.close()

    assert task_count == 1


def test_same_idempotency_key_with_different_payload_returns_conflict(test_app):
    client, _ = test_app

    first_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "conflict-key"},
        json={"title": "Task A"},
    )
    second_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "conflict-key"},
        json={"title": "Different task"},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {
        "detail": "Idempotency key has already been used with a different request"
    }


def test_get_all_tasks(test_app):
    client, _ = test_app

    client.post(
        "/tasks",
        headers={"Idempotency-Key": "list-task-one"},
        json={"title": "First task"},
    )
    client.post(
        "/tasks",
        headers={"Idempotency-Key": "list-task-two"},
        json={"title": "Second task"},
    )

    response = client.get("/tasks")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["title"] == "First task"
    assert data[1]["title"] == "Second task"


def test_get_existing_task(test_app):
    client, _ = test_app

    create_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "get-existing-task"},
        json={
            "title": "Prepare report",
            "description": "Prepare weekly report",
        },
    )
    task_id = create_response.json()["id"]

    response = client.get(f"/tasks/{task_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["title"] == "Prepare report"
    assert data["description"] == "Prepare weekly report"


def test_get_nonexistent_task(test_app):
    client, _ = test_app

    response = client.get("/tasks/not-a-real-task")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_update_task(test_app):
    client, _ = test_app

    create_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "update-task"},
        json={
            "title": "Original title",
            "description": "Original description",
        },
    )
    task_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updatedAt"]

    response = client.patch(
        f"/tasks/{task_id}",
        json={
            "title": "  Updated title  ",
            "description": None,
            "status": "completed",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["title"] == "Updated title"
    assert data["description"] is None
    assert data["status"] == "completed"
    assert data["updatedAt"] != original_updated_at


def test_update_task_with_invalid_title(test_app):
    client, _ = test_app

    create_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "invalid-update-title"},
        json={"title": "Original title"},
    )
    task_id = create_response.json()["id"]

    response = client.patch(
        f"/tasks/{task_id}",
        json={"title": "   "},
    )

    assert response.status_code == 422


def test_update_task_with_invalid_status(test_app):
    client, _ = test_app

    create_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "invalid-update-status"},
        json={"title": "Original title"},
    )
    task_id = create_response.json()["id"]

    response = client.patch(
        f"/tasks/{task_id}",
        json={"status": "in_progress"},
    )

    assert response.status_code == 422


def test_update_nonexistent_task(test_app):
    client, _ = test_app

    response = client.patch(
        "/tasks/not-a-real-task",
        json={"title": "Updated title"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_mark_task_as_completed(test_app):
    client, _ = test_app

    create_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "complete-task"},
        json={"title": "Finish case study"},
    )
    task_id = create_response.json()["id"]
    original_updated_at = create_response.json()["updatedAt"]

    response = client.patch(f"/tasks/{task_id}/complete")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == task_id
    assert data["status"] == "completed"
    assert data["updatedAt"] != original_updated_at

    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.json()["status"] == "completed"


def test_complete_nonexistent_task(test_app):
    client, _ = test_app

    response = client.patch("/tasks/not-a-real-task/complete")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_delete_task(test_app):
    client, _ = test_app

    create_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "delete-task"},
        json={"title": "Task to delete"},
    )
    task_id = create_response.json()["id"]

    response = client.delete(f"/tasks/{task_id}")

    assert response.status_code == 204
    assert response.content == b""

    get_response = client.get(f"/tasks/{task_id}")
    assert get_response.status_code == 404


def test_delete_nonexistent_task(test_app):
    client, _ = test_app

    response = client.delete("/tasks/not-a-real-task")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


def test_filter_by_pending_status(test_app):
    client, _ = test_app

    client.post(
        "/tasks",
        headers={"Idempotency-Key": "pending-filter-pending"},
        json={"title": "Pending task"},
    )
    completed_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "pending-filter-completed"},
        json={"title": "Completed task"},
    )
    completed_task_id = completed_response.json()["id"]
    client.patch(f"/tasks/{completed_task_id}/complete")

    response = client.get("/tasks?status=pending")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Pending task"
    assert data[0]["status"] == "pending"


def test_filter_by_completed_status(test_app):
    client, _ = test_app

    client.post(
        "/tasks",
        headers={"Idempotency-Key": "completed-filter-pending"},
        json={"title": "Pending task"},
    )
    completed_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "completed-filter-completed"},
        json={"title": "Completed task"},
    )
    completed_task_id = completed_response.json()["id"]
    client.patch(f"/tasks/{completed_task_id}/complete")

    response = client.get("/tasks?status=completed")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Completed task"
    assert data[0]["status"] == "completed"


def test_filter_by_creation_date(test_app):
    client, SessionLocal = test_app

    old_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "old-date-task"},
        json={"title": "Old task"},
    )
    new_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "new-date-task"},
        json={"title": "New task"},
    )

    db = SessionLocal()
    try:
        old_task = db.get(Task, old_response.json()["id"])
        new_task = db.get(Task, new_response.json()["id"])
        old_task.created_at = datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC)
        new_task.created_at = datetime(2026, 8, 20, 10, 0, 0, tzinfo=UTC)
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/tasks?created_from=2026-08-10T00:00:00Z"
        "&created_to=2026-08-31T23:59:59Z"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "New task"


def test_filter_by_status_and_creation_date(test_app):
    client, SessionLocal = test_app

    old_completed_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "old-completed-task"},
        json={"title": "Old completed task"},
    )
    new_pending_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "new-pending-task"},
        json={"title": "New pending task"},
    )
    new_completed_response = client.post(
        "/tasks",
        headers={"Idempotency-Key": "new-completed-task"},
        json={"title": "New completed task"},
    )

    client.patch(f"/tasks/{old_completed_response.json()['id']}/complete")
    client.patch(f"/tasks/{new_completed_response.json()['id']}/complete")

    db = SessionLocal()
    try:
        old_completed = db.get(Task, old_completed_response.json()["id"])
        new_pending = db.get(Task, new_pending_response.json()["id"])
        new_completed = db.get(Task, new_completed_response.json()["id"])
        old_completed.created_at = datetime(2026, 8, 1, 10, 0, 0, tzinfo=UTC)
        new_pending.created_at = datetime(2026, 8, 20, 10, 0, 0, tzinfo=UTC)
        new_completed.created_at = datetime(2026, 8, 21, 10, 0, 0, tzinfo=UTC)
        db.commit()
    finally:
        db.close()

    response = client.get(
        "/tasks?status=completed"
        "&created_from=2026-08-10T00:00:00Z"
        "&created_to=2026-08-31T23:59:59Z"
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "New completed task"
    assert data[0]["status"] == "completed"


def test_invalid_creation_date_range(test_app):
    client, _ = test_app

    response = client.get(
        "/tasks?created_from=2026-08-31T23:59:59Z"
        "&created_to=2026-08-01T00:00:00Z"
    )

    assert response.status_code == 422
    assert response.json() == {"detail": "created_from cannot be after created_to"}
