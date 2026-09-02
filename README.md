# Builders' Tribe Task API

Good day! This is my solution for the Builders' Tribe Engineering Intern case study: a small FastAPI backend for creating and managing tasks.

I chose to keep the project deliberately plain as the main goal here was to make the API correct, testable, and easy to explain line by line while ensuring that it's still high quality code.

## Selected Extra Requirement

Option B - Filtering

## What I Built

The API supports the required task operations:

| Method | Endpoint | What it does |
| --- | --- | --- |
| POST | `/tasks` | Creates a task |
| GET | `/tasks` | Lists tasks |
| GET | `/tasks/{task_id}` | Gets one task |
| PATCH | `/tasks/{task_id}` | Updates a task |
| PATCH | `/tasks/{task_id}/complete` | Marks a task as completed |
| DELETE | `/tasks/{task_id}` | Deletes a task |

For filtering, `GET /tasks` can filter by status and creation date:

```text
GET /tasks?status=pending
GET /tasks?status=completed
GET /tasks?created_from=2026-08-01T00:00:00Z
GET /tasks?created_to=2026-08-31T23:59:59Z
GET /tasks?status=completed&created_from=2026-08-01T00:00:00Z&created_to=2026-08-31T23:59:59Z
```

The filtering happens in the SQLAlchemy query instead of loading every task and filtering in Python.

## Stack

This project uses:

- Python 3.11+
- FastAPI and Pydantic for the API layer and validation
- SQLAlchemy with SQLite for persistence
- Uvicorn to run the app locally
- pytest with FastAPI's TestClient for tests

I used SQLite because it keeps the project easy to run for a take-home case study.

## Project Layout

```text
app/
  main.py            # creates the FastAPI app and registers routes
  database.py        # SQLAlchemy engine, session, Base, and get_db
  models.py          # database table model
  schemas.py         # request/response validation models
  routers/
    tasks.py         # task endpoints
tests/
  test_tasks.py
requirements.txt
README.md
.gitignore
```

`models.py` and `schemas.py` are separate on purpose. The model describes how a task is stored in the database. The schemas describe what the API accepts and returns.

## Running It Locally

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```bash
.\.venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the app:

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

The health check is:

```text
GET /
```

and returns:

```json
{
  "status": "ok"
}
```

FastAPI's generated docs are available at:

```text
http://127.0.0.1:8000/docs
http://127.0.0.1:8000/openapi.json
```

## Database

The app creates `db.sqlite3` automatically when it starts. The database file is ignored by Git.

The `tasks` table stores:

- `id`
- `title`
- `description`
- `status`
- `created_at`
- `updated_at`
- `idempotency_key`
- `request_fingerprint`

The API returns timestamp fields as `createdAt` and `updatedAt`, but the Python code keeps normal snake_case names internally.

Example task response:

```json
{
  "id": "uuid-string",
  "title": "Prepare report",
  "description": "Prepare weekly report",
  "status": "pending",
  "createdAt": "2026-08-31T09:00:00",
  "updatedAt": "2026-08-31T09:00:00"
}
```

## Creating Tasks And Idempotency

`POST /tasks` requires an `Idempotency-Key` header. I added this because the case study asks that an accidental duplicate POST should not create the same task twice.

Example:

```bash
curl -X POST http://127.0.0.1:8000/tasks \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: abc-123" \
  -d "{\"title\":\"Prepare report\",\"description\":\"Prepare weekly report\"}"
```

A new key creates a task and returns `201 Created`.

If the same key is sent again with the same request body, the API returns the original task instead of inserting another row. That second response is `200 OK`.

If the same key is reused with a different body, the API returns:

```json
{
  "detail": "Idempotency key has already been used with a different request"
}
```

with `409 Conflict`.

I did not make task titles unique, because two real tasks can reasonably have the same title. The idempotency key is the thing that must be unique. I also store a small SHA-256 fingerprint of the create request so the API can tell whether a repeated key has the same payload or a different one.

## Reading, Updating, Completing, And Deleting

List tasks:

```bash
curl http://127.0.0.1:8000/tasks
```

Get one task:

```bash
curl http://127.0.0.1:8000/tasks/{task_id}
```

Update a task:

```bash
curl -X PATCH http://127.0.0.1:8000/tasks/{task_id} \
  -H "Content-Type: application/json" \
  -d "{\"title\":\"Updated title\",\"description\":null,\"status\":\"completed\"}"
```

Only `title`, `description`, and `status` are editable through PATCH. Clients cannot directly change the task id, timestamps, or idempotency fields.

Mark complete:

```bash
curl -X PATCH http://127.0.0.1:8000/tasks/{task_id}/complete
```

Delete:

```bash
curl -X DELETE http://127.0.0.1:8000/tasks/{task_id}
```

Delete returns `204 No Content`.

## Validation And Errors

Task titles are required when creating a task. They are trimmed before saving, cannot be blank, and are limited to 200 characters.

Descriptions are optional, may be `null`, and are limited to 1000 characters.

Status can only be:

- `pending`
- `completed`

Invalid request data returns `422`.

Missing tasks return:

```json
{
  "detail": "Task not found"
}
```

with `404 Not Found`.

For filtering, `created_from` cannot be after `created_to`. If that happens, the API returns:

```json
{
  "detail": "created_from cannot be after created_to"
}
```

## Tests

Run the tests with:

```bash
pytest
```

The tests use a temporary SQLite database, so they do not touch the normal local `db.sqlite3` file.

The test suite covers the main required behavior: creating, reading, updating, completing, deleting, filtering, validation errors, missing tasks, and duplicate POST protection.

## Assumptions I Made

This is a single-user task API because I chose filtering instead of authentication. New tasks start as `pending`, completed tasks can still be edited, and idempotency protection only applies to task creation.

I store timestamps using UTC. Filtering by date uses the task creation timestamp.

## Known Limitations

SQLite is fine for this assessment, but I would not use this exact database setup for a high-concurrency production app.

There is no authentication, no pagination, and no cleanup process for old idempotency records. I left those out because they were outside the selected case study scope.

## One Thing I Would Improve Next

The first step would be adding a `users` table and connecting each task to a user with a `user_id` foreign key. After that, every task query would filter by the current user. For instance, `GET /tasks` would only return tasks owned by the signed-in user, and `GET /tasks/{task_id}` would return `404` if the task either does not exist or belongs to someone else.

Second, I would not store plain text passwords. Passwords should be hashed with a password hashing library before they are saved. For login, I would use token-based authentication so each request can identify the current user without sending the password again.

Third, I would also update the tests before changing too much code. The important tests would check that one user cannot read, update, complete, or delete another user's tasks. That would keep the main rule clear: every task belongs to one user, and the API should enforce that rule in every endpoint.

Lastly, I did not include this now because authentication was not the selected option for the case study. Adding it properly would touch the database model, request flow, route dependencies, and tests, so I left it as a future improvement instead of adding a rushed version.
