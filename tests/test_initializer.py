"""Tests for initializer.py - Project initialization."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from claude_harness.initializer import (
    HarnessConfig,
    Initializer,
    initialize_project,
)


class TestHarnessConfig:
    """Tests for HarnessConfig dataclass."""

    def test_harness_config_defaults(self):
        """Test default values."""
        config = HarnessConfig()
        assert config.project_name == ""
        assert config.language == "python"
        assert config.port == 8000
        assert config.protected_branches == ["main", "master"]
        assert config.context_budget == 200000

    def test_harness_config_custom(self):
        """Test custom values."""
        config = HarnessConfig(
            project_name="my-project",
            language="typescript",
            framework="nextjs",
            port=3000,
        )
        assert config.project_name == "my-project"
        assert config.language == "typescript"
        assert config.framework == "nextjs"
        assert config.port == 3000

    def test_harness_config_to_dict(self):
        """Test config serialization."""
        config = HarnessConfig(
            project_name="test",
            language="python",
            framework="flask",
        )
        data = config.to_dict()
        assert data["project_name"] == "test"
        assert data["stack"]["language"] == "python"
        assert data["stack"]["framework"] == "flask"

    def test_harness_config_to_dict_structure(self):
        """Test config dict structure."""
        config = HarnessConfig(
            project_name="test",
            port=5000,
            health_endpoint="/health",
        )
        data = config.to_dict()

        # Check structure
        assert "project_name" in data
        assert "stack" in data
        assert "startup" in data
        assert "git" in data
        assert "testing" in data
        assert "context_tracking" in data

        # Check nested values
        assert data["startup"]["port"] == 5000
        assert data["startup"]["health_endpoint"] == "/health"


class TestInitializerFileGeneration:
    """Tests for Initializer file generation."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        return tmp_path

    @pytest.fixture
    def initializer(self, temp_project):
        """Create an Initializer with minimal config."""
        init = Initializer(str(temp_project))
        init.config = HarnessConfig(
            project_name="test-project",
            language="python",
            framework="flask",
            database="postgresql",
            port=5000,
            health_endpoint="/api/health",
            start_command="python run.py",
            test_framework="pytest",
            e2e_enabled=True,
            e2e_base_url="http://localhost:5000",
            initial_phase="Phase 1",
            initial_features=["Feature 1", "Feature 2"],
            create_claude_hooks=False,
        )
        return init

    def test_write_config(self, initializer, temp_project):
        """Test config.json generation."""
        harness_dir = temp_project / ".claude-harness"
        harness_dir.mkdir()

        initializer._write_config()

        config_file = harness_dir / "config.json"
        assert config_file.exists()

        data = json.loads(config_file.read_text())
        assert data["project_name"] == "test-project"
        assert data["stack"]["language"] == "python"

    def test_write_features(self, initializer, temp_project):
        """Test features.json generation."""
        harness_dir = temp_project / ".claude-harness"
        harness_dir.mkdir()

        initializer._write_features()

        features_file = harness_dir / "features.json"
        assert features_file.exists()

        data = json.loads(features_file.read_text())
        assert data["current_phase"] == "Phase 1"
        assert len(data["features"]) == 2

    def test_write_progress(self, initializer, temp_project):
        """Test progress.md generation."""
        harness_dir = temp_project / ".claude-harness"
        harness_dir.mkdir()

        initializer._write_progress()

        progress_file = harness_dir / "progress.md"
        assert progress_file.exists()

        content = progress_file.read_text()
        assert "Session Progress Log" in content
        assert "Completed This Session" in content

    def test_write_init_script(self, initializer, temp_project):
        """Test init.sh generation."""
        scripts_dir = temp_project / "scripts"
        scripts_dir.mkdir()

        initializer._write_init_script()

        init_script = scripts_dir / "init.sh"
        assert init_script.exists()

        content = init_script.read_text()
        assert "#!/bin/bash" in content
        assert "claude-harness" in content

    def test_write_init_powershell(self, initializer, temp_project):
        """Test init.ps1 generation."""
        scripts_dir = temp_project / "scripts"
        scripts_dir.mkdir()

        initializer._write_init_powershell()

        init_script = scripts_dir / "init.ps1"
        assert init_script.exists()

        content = init_script.read_text()
        assert "PowerShell" in content or "claude-harness" in content

    def test_write_hooks(self, initializer, temp_project):
        """Test hook scripts generation."""
        harness_dir = temp_project / ".claude-harness"
        harness_dir.mkdir()
        hooks_dir = harness_dir / "hooks"
        hooks_dir.mkdir()

        initializer._write_hooks()

        assert hooks_dir.exists()

        # Check hook scripts
        git_safety = hooks_dir / "check-git-safety.sh"
        assert git_safety.exists()

        log_activity = hooks_dir / "log-activity.sh"
        assert log_activity.exists()

        # Check new tracking hooks (read JSON from stdin)
        track_read = hooks_dir / "track-read.sh"
        assert track_read.exists()

        track_write = hooks_dir / "track-write.sh"
        assert track_write.exists()

        track_edit = hooks_dir / "track-edit.sh"
        assert track_edit.exists()

        session_stop = hooks_dir / "session-stop.sh"
        assert session_stop.exists()

    def test_write_e2e_setup(self, initializer, temp_project):
        """Test E2E setup generation."""
        # Create required directories first (normally done by _generate_files)
        e2e_dir = temp_project / "e2e"
        e2e_dir.mkdir()
        tests_dir = e2e_dir / "tests"
        tests_dir.mkdir()

        initializer._write_e2e_setup()

        assert e2e_dir.exists()

        conftest = e2e_dir / "conftest.py"
        assert conftest.exists()

        pytest_ini = e2e_dir / "pytest.ini"
        assert pytest_ini.exists()

        example_test = tests_dir / "test_example.py"
        assert example_test.exists()


class TestInitializerClaudeSettings:
    """Tests for Claude settings generation."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project directory."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        return tmp_path

    @pytest.fixture
    def initializer(self, temp_project):
        """Create an Initializer with hooks enabled."""
        init = Initializer(str(temp_project))
        init.config = HarnessConfig(
            project_name="test-project",
            create_claude_hooks=True,
        )
        return init

    def test_write_claude_settings_new(self, initializer, temp_project):
        """Test creating new .claude/settings.json."""
        initializer._write_claude_settings()

        settings_file = temp_project / ".claude" / "settings.json"
        assert settings_file.exists()

        data = json.loads(settings_file.read_text())
        assert "hooks" in data
        assert "PreToolUse" in data["hooks"]
        assert "PostToolUse" in data["hooks"]
        assert "Stop" in data["hooks"]

    def test_write_claude_settings_merge(self, initializer, temp_project):
        """Test merging with existing .claude/settings.json."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir()

        # Create existing settings
        existing = {
            "custom_setting": "value",
            "hooks": {
                "PreToolUse": [{"matcher": "custom", "command": "echo custom"}]
            },
        }
        with open(claude_dir / "settings.json", "w") as f:
            json.dump(existing, f)

        initializer._write_claude_settings()

        data = json.loads((claude_dir / "settings.json").read_text())

        # Should preserve existing
        assert data["custom_setting"] == "value"
        # Should have merged hooks
        assert len(data["hooks"]["PreToolUse"]) >= 2


class TestInitializerDetection:
    """Tests for stack detection integration."""

    @pytest.fixture
    def python_project(self, tmp_path):
        """Create a Python project."""
        (tmp_path / "requirements.txt").write_text("flask>=2.0\npytest\n")
        (tmp_path / ".git").mkdir()
        return tmp_path

    def test_detect_existing_stack(self, python_project):
        """Test detection of existing stack."""
        init = Initializer(str(python_project))
        init._detect_existing_stack()

        assert init.detected is not None
        assert init.detected.language == "python"

    def test_default_port_python(self, python_project):
        """Test default port for Python projects."""
        init = Initializer(str(python_project))
        init.config = HarnessConfig(language="python", framework="flask")

        port = init._get_default_port()
        assert port == 5000  # Flask default

    def test_default_port_javascript(self, tmp_path):
        """Test default port for JavaScript projects."""
        (tmp_path / "package.json").write_text('{"name": "test"}')

        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(language="javascript", framework="express")

        port = init._get_default_port()
        assert port == 3000  # Express default


class TestInitializerIntegration:
    """Integration tests for full initialization."""

    @pytest.fixture
    def temp_project(self, tmp_path):
        """Create a temporary project."""
        return tmp_path

    @patch("claude_harness.initializer.questionary")
    def test_full_initialization(self, mock_questionary, temp_project):
        """Test full initialization flow with mocked prompts."""
        # Mock all questionary calls
        mock_questionary.text.return_value.ask.return_value = "test-project"
        mock_questionary.select.return_value.ask.return_value = "python"
        mock_questionary.confirm.return_value.ask.return_value = True

        # Create initializer and set config directly (bypass interactive)
        init = Initializer(str(temp_project))
        init.config = HarnessConfig(
            project_name="test-project",
            language="python",
            framework="flask",
            database="postgresql",
            port=5000,
            test_framework="pytest",
            e2e_enabled=True,
            e2e_base_url="http://localhost:5000",
            initial_phase="Phase 1",
            create_claude_hooks=False,
        )

        # Run file generation
        init._generate_files()

        # Verify all files created
        harness_dir = temp_project / ".claude-harness"
        assert harness_dir.exists()
        assert (harness_dir / "config.json").exists()
        assert (harness_dir / "features.json").exists()
        assert (harness_dir / "progress.md").exists()
        assert (harness_dir / "hooks").exists()

        scripts_dir = temp_project / "scripts"
        assert scripts_dir.exists()
        assert (scripts_dir / "init.sh").exists()
        assert (scripts_dir / "init.ps1").exists()

        e2e_dir = temp_project / "e2e"
        assert e2e_dir.exists()


class TestInitializeProjectFunction:
    """Tests for initialize_project convenience function."""

    @patch("claude_harness.initializer.Initializer")
    def test_initialize_project(self, mock_initializer_class, tmp_path):
        """Test the convenience function."""
        mock_instance = MagicMock()
        mock_instance.run.return_value = HarnessConfig(project_name="test")
        mock_initializer_class.return_value = mock_instance

        result = initialize_project(str(tmp_path))

        mock_initializer_class.assert_called_once_with(str(tmp_path), non_interactive=False)
        mock_instance.run.assert_called_once()

    @patch("claude_harness.initializer.Initializer")
    def test_initialize_project_non_interactive(self, mock_initializer_class, tmp_path):
        """Test the convenience function with non-interactive mode."""
        mock_instance = MagicMock()
        mock_instance.run.return_value = HarnessConfig(project_name="test")
        mock_initializer_class.return_value = mock_instance

        result = initialize_project(str(tmp_path), non_interactive=True)

        mock_initializer_class.assert_called_once_with(str(tmp_path), non_interactive=True)
        mock_instance.run.assert_called_once()


class TestInitializerNonInteractive:
    """Tests for non-interactive initialization mode."""

    def test_non_interactive_creates_files(self, tmp_path):
        """Test that non-interactive mode creates all required files."""
        init = Initializer(str(tmp_path), non_interactive=True)
        config = init.run()

        # Should have used directory name as project name
        assert config.project_name == tmp_path.name

        # Should have created harness files
        harness_dir = tmp_path / ".claude-harness"
        assert harness_dir.exists()
        assert (harness_dir / "config.json").exists()
        assert (harness_dir / "features.json").exists()
        assert (harness_dir / "progress.md").exists()

        # Should have created scripts
        scripts_dir = tmp_path / "scripts"
        assert scripts_dir.exists()
        assert (scripts_dir / "init.sh").exists()

        # Should have enabled Claude hooks
        assert (tmp_path / ".claude" / "settings.json").exists()

    def test_non_interactive_uses_detected_values(self, tmp_path):
        """Test that non-interactive mode uses detected stack values."""
        # Create a Python project
        (tmp_path / "requirements.txt").write_text("flask>=2.0\npytest\n")
        (tmp_path / ".git").mkdir()

        init = Initializer(str(tmp_path), non_interactive=True)
        config = init.run()

        # Should have detected Python
        assert config.language == "python"
        # Should have detected Flask (detector may return capitalized)
        assert config.framework.lower() == "flask"
        # Should have detected pytest
        assert config.test_framework == "pytest"

    def test_non_interactive_defaults_for_new_project(self, tmp_path):
        """Test that non-interactive mode uses sensible defaults for new projects."""
        init = Initializer(str(tmp_path), non_interactive=True)
        config = init.run()

        # Should use defaults
        assert config.language == "python"
        assert config.test_framework == "pytest"
        assert config.venv_path == "venv"
        assert config.env_file == ".env"
        assert config.test_directory == "tests"
        assert config.e2e_enabled is True
        assert config.create_claude_hooks is True


class TestInitializerEdgeCases:
    """Edge case tests for Initializer."""

    def test_existing_harness_directory(self, tmp_path):
        """Test initialization with existing .claude-harness directory."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()
        (harness_dir / "old_file.txt").write_text("old content")

        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(project_name="test")

        # Should not raise
        init._generate_files()

        # Old file should still exist
        assert (harness_dir / "old_file.txt").exists()

    def test_special_characters_in_project_name(self, tmp_path):
        """Test project name with special characters."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="my-project_v2.0",
            language="python",
        )

        init._generate_files()

        config_file = tmp_path / ".claude-harness" / "config.json"
        data = json.loads(config_file.read_text())
        assert data["project_name"] == "my-project_v2.0"

    def test_no_e2e_setup(self, tmp_path):
        """Test initialization without E2E."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test",
            e2e_enabled=False,
        )

        init._generate_files()

        e2e_dir = tmp_path / "e2e"
        assert not e2e_dir.exists()
