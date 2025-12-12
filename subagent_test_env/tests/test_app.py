"""Unit tests for the Flask task API."""

import pytest
from app import app


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def clear_tasks():
    """Clear tasks before each test."""
    from app import tasks
    tasks.clear()


def test_health_check(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "healthy"
    assert data["service"] == "task-api"


def test_get_tasks_empty(client):
    """Test getting tasks when none exist."""
    response = client.get("/api/v1/tasks")
    assert response.status_code == 200
    data = response.get_json()
    assert data["tasks"] == []
    assert data["count"] == 0


def test_create_task(client):
    """Test creating a new task."""
    response = client.post(
        "/api/v1/tasks",
        json={"title": "Test Task", "description": "A test task"}
    )
    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == "Test Task"
    assert data["description"] == "A test task"
    assert data["completed"] is False
    assert "id" in data


def test_create_task_no_title(client):
    """Test creating a task without a title fails."""
    response = client.post("/api/v1/tasks", json={})
    assert response.status_code == 400


def test_get_task_by_id(client):
    """Test getting a specific task by ID."""
    # First create a task
    client.post("/api/v1/tasks", json={"title": "Find Me"})

    # Then get it
    response = client.get("/api/v1/tasks/1")
    assert response.status_code == 200
    data = response.get_json()
    assert data["title"] == "Find Me"


def test_get_task_not_found(client):
    """Test getting a non-existent task returns 404."""
    response = client.get("/api/v1/tasks/999")
    assert response.status_code == 404


def test_complete_task(client):
    """Test marking a task as completed."""
    client.post("/api/v1/tasks", json={"title": "Complete Me"})

    response = client.post("/api/v1/tasks/1/complete")
    assert response.status_code == 200
    data = response.get_json()
    assert data["completed"] is True
