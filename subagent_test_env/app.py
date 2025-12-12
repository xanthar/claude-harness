"""Simple Flask API for testing claude-harness integration."""

from flask import Flask, jsonify, request

app = Flask(__name__)

# In-memory storage for tasks
tasks = []


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "healthy", "service": "task-api"})


@app.route("/api/v1/tasks", methods=["GET"])
def get_tasks():
    """Get all tasks."""
    return jsonify({"tasks": tasks, "count": len(tasks)})


@app.route("/api/v1/tasks", methods=["POST"])
def create_task():
    """Create a new task."""
    data = request.get_json()
    if not data or "title" not in data:
        return jsonify({"error": "Title is required"}), 400

    task = {
        "id": len(tasks) + 1,
        "title": data["title"],
        "description": data.get("description", ""),
        "completed": False
    }
    tasks.append(task)
    return jsonify(task), 201


@app.route("/api/v1/tasks/<int:task_id>", methods=["GET"])
def get_task(task_id):
    """Get a specific task by ID."""
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)


@app.route("/api/v1/tasks/<int:task_id>/complete", methods=["POST"])
def complete_task(task_id):
    """Mark a task as completed."""
    task = next((t for t in tasks if t["id"] == task_id), None)
    if task is None:
        return jsonify({"error": "Task not found"}), 404
    task["completed"] = True
    return jsonify(task)


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
