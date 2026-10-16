"""CRUD, validation and error-response tests for /api/tasks."""

import pytest


# ---------- create ----------

def test_create_task_returns_201_and_the_new_task(client):
    response = client.post(
        "/api/tasks", json={"title": "Learn Docker", "description": "Start with images"}
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"] >= 1
    assert body["title"] == "Learn Docker"
    assert body["description"] == "Start with images"
    assert body["completed"] is False
    assert "created_at" in body and "updated_at" in body


def test_create_task_trims_whitespace_and_turns_blank_description_into_null(client):
    response = client.post("/api/tasks", json={"title": "  Padded  ", "description": "   "})

    assert response.status_code == 201
    assert response.json()["title"] == "Padded"
    assert response.json()["description"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},  # title missing
        {"title": ""},  # empty
        {"title": "    "},  # only spaces
        {"title": "x" * 201},  # too long
        {"title": "ok", "description": "y" * 2001},  # description too long
        {"title": "ok", "completed": "maybe"},  # not a boolean
        {"title": 123},  # wrong type
    ],
)
def test_create_task_rejects_invalid_data_with_422(client, payload):
    response = client.post("/api/tasks", json=payload)

    assert response.status_code == 422
    assert "detail" in response.json()


def test_create_task_rejects_non_json_body(client):
    response = client.post(
        "/api/tasks", content="not json", headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422


# ---------- list ----------

def test_list_tasks_is_empty_at_first(client):
    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert response.json() == []


def test_list_tasks_returns_newest_first(client, make_task):
    first = make_task("first")
    second = make_task("second")

    response = client.get("/api/tasks")

    assert response.status_code == 200
    assert [t["id"] for t in response.json()] == [second["id"], first["id"]]


# ---------- read one ----------

def test_get_task_by_id(client, make_task):
    created = make_task("Find me")

    response = client.get(f"/api/tasks/{created['id']}")

    assert response.status_code == 200
    assert response.json() == created


def test_get_missing_task_returns_404(client):
    response = client.get("/api/tasks/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


@pytest.mark.parametrize("bad_id", ["abc", "0", "-5", "99999999999"])
def test_get_task_with_invalid_id_returns_422(client, bad_id):
    assert client.get(f"/api/tasks/{bad_id}").status_code == 422


# ---------- update ----------

def test_update_task_replaces_its_fields(client, make_task):
    created = make_task("Old title")

    response = client.put(
        f"/api/tasks/{created['id']}",
        json={"title": "New title", "description": "Now with details", "completed": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["title"] == "New title"
    assert body["description"] == "Now with details"
    assert body["completed"] is True
    # The change is really stored, not just echoed back.
    assert client.get(f"/api/tasks/{created['id']}").json()["title"] == "New title"


def test_update_missing_task_returns_404(client):
    response = client.put("/api/tasks/999999", json={"title": "Nope", "completed": False})

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "No completed field"},  # PUT needs every field
        {"completed": True},  # title missing
        {"title": "", "completed": False},
        {"title": "x" * 201, "completed": False},
    ],
)
def test_update_task_rejects_invalid_data_with_422(client, make_task, payload):
    created = make_task("Keep me")

    response = client.put(f"/api/tasks/{created['id']}", json=payload)

    assert response.status_code == 422
    # A rejected update must not change the stored task.
    assert client.get(f"/api/tasks/{created['id']}").json()["title"] == "Keep me"


# ---------- delete ----------

def test_delete_task_returns_204_and_removes_it(client, make_task):
    created = make_task("Delete me")

    response = client.delete(f"/api/tasks/{created['id']}")

    assert response.status_code == 204
    assert response.content == b""
    assert client.get(f"/api/tasks/{created['id']}").status_code == 404
    assert client.get("/api/tasks").json() == []


def test_delete_missing_task_returns_404(client):
    response = client.delete("/api/tasks/999999")

    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found"}
