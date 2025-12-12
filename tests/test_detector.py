"""Tests for stack detector."""
import pytest
import tempfile
from pathlib import Path

from claude_harness.detector import StackDetector, detect_stack


class TestStackDetector:
    """Test stack detection functionality."""

    def test_detect_empty_directory(self, tmp_path):
        """Test detection in empty directory."""
        detected = detect_stack(str(tmp_path))

        assert detected.language is None
        assert detected.framework is None
        assert detected.confidence < 0.3

    def test_detect_python_requirements(self, tmp_path):
        """Test Python detection via requirements.txt."""
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("flask>=3.0\nsqlalchemy>=2.0\npytest\n")

        detected = detect_stack(str(tmp_path))

        assert detected.language == "python"
        assert detected.framework == "Flask"
        assert detected.orm == "SQLAlchemy"
        assert detected.test_framework == "pytest"

    def test_detect_javascript_package_json(self, tmp_path):
        """Test JavaScript detection via package.json."""
        pkg_file = tmp_path / "package.json"
        pkg_file.write_text('{"dependencies": {"react": "^18.0", "jest": "^29.0"}}')

        detected = detect_stack(str(tmp_path))

        assert detected.language == "javascript"
        assert detected.framework == "React"
        assert detected.test_framework == "Jest"

    def test_detect_typescript(self, tmp_path):
        """Test TypeScript detection."""
        pkg_file = tmp_path / "package.json"
        pkg_file.write_text('{"dependencies": {"typescript": "^5.0", "express": "^4.0"}}')

        detected = detect_stack(str(tmp_path))

        assert detected.language == "typescript"
        assert detected.framework == "Express.js"

    def test_detect_git(self, tmp_path):
        """Test Git detection."""
        (tmp_path / ".git").mkdir()

        detected = detect_stack(str(tmp_path))

        assert detected.has_git is True

    def test_detect_docker(self, tmp_path):
        """Test Docker detection."""
        (tmp_path / "Dockerfile").touch()

        detected = detect_stack(str(tmp_path))

        assert detected.has_docker is True

    def test_detect_kubernetes(self, tmp_path):
        """Test Kubernetes detection."""
        (tmp_path / "kubernetes").mkdir()

        detected = detect_stack(str(tmp_path))

        assert detected.has_kubernetes is True

    def test_detect_github_actions(self, tmp_path):
        """Test GitHub Actions CI detection."""
        workflows = tmp_path / ".github" / "workflows"
        workflows.mkdir(parents=True)
        (workflows / "ci.yml").touch()

        detected = detect_stack(str(tmp_path))

        assert detected.has_ci is True
        assert detected.ci_provider == "GitHub Actions"

    def test_detect_postgresql_from_env(self, tmp_path):
        """Test PostgreSQL detection from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("DATABASE_URL=postgresql://user:pass@localhost/db")

        detected = detect_stack(str(tmp_path))

        assert detected.database == "PostgreSQL"
        assert detected.env_file == ".env"

    def test_detect_claude_md(self, tmp_path):
        """Test existing CLAUDE.md detection."""
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        (claude_dir / "CLAUDE.md").write_text("# Project")

        detected = detect_stack(str(tmp_path))

        assert detected.has_claude_md is True

    def test_detect_backend_directory(self, tmp_path):
        """Test detection in backend subdirectory."""
        backend = tmp_path / "backend"
        backend.mkdir()
        (backend / "requirements.txt").write_text("django>=4.0")
        (backend / "venv" / "bin").mkdir(parents=True)
        (backend / "venv" / "bin" / "activate").touch()

        detected = detect_stack(str(tmp_path))

        assert detected.language == "python"
        assert detected.framework == "Django"
        assert "backend" in (detected.venv_path or "")

    def test_confidence_calculation(self, tmp_path):
        """Test confidence score calculation."""
        # Minimal project
        detected_minimal = detect_stack(str(tmp_path))

        # Full project
        (tmp_path / ".git").mkdir()
        (tmp_path / "requirements.txt").write_text("flask\nsqlalchemy\npytest")
        (tmp_path / ".env").write_text("DATABASE_URL=postgresql://localhost/db")
        (tmp_path / "tests").mkdir()
        (tmp_path / "app").mkdir()

        detected_full = detect_stack(str(tmp_path))

        assert detected_full.confidence > detected_minimal.confidence
        assert detected_full.confidence >= 0.5
