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
        """Test creating new .claude/settings.local.json."""
        initializer._write_claude_settings()

        settings_file = temp_project / ".claude" / "settings.local.json"
        assert settings_file.exists()

        data = json.loads(settings_file.read_text())
        assert "hooks" in data
        assert "PreToolUse" in data["hooks"]
        assert "PostToolUse" in data["hooks"]
        assert "SessionEnd" in data["hooks"]

    def test_write_claude_settings_merge(self, initializer, temp_project):
        """Test merging with existing .claude/settings.local.json."""
        claude_dir = temp_project / ".claude"
        claude_dir.mkdir()

        # Create existing settings
        existing = {
            "custom_setting": "value",
            "hooks": {
                "PreToolUse": [{"matcher": "custom", "command": "echo custom"}]
            },
        }
        with open(claude_dir / "settings.local.json", "w") as f:
            json.dump(existing, f)

        initializer._write_claude_settings()

        data = json.loads((claude_dir / "settings.local.json").read_text())

        # Should preserve existing
        assert data["custom_setting"] == "value"
        # Should have merged hooks
        assert len(data["hooks"]["PreToolUse"]) >= 2

    def test_default_permissions_python(self, temp_project):
        """Test default permissions generated for Python projects."""
        init = Initializer(str(temp_project))
        init.config = HarnessConfig(
            project_name="test-project",
            language="python",
            create_claude_hooks=True,
        )

        permissions = init._get_default_permissions()

        # Common permissions
        assert "Bash(git:*)" in permissions
        assert "Bash(claude-harness:*)" in permissions
        assert "WebSearch" in permissions

        # Python-specific
        assert "Bash(python:*)" in permissions
        assert "Bash(pytest:*)" in permissions
        assert "Bash(.venv/bin/*:*)" in permissions

    def test_default_permissions_javascript(self, temp_project):
        """Test default permissions generated for JavaScript projects."""
        init = Initializer(str(temp_project))
        init.config = HarnessConfig(
            project_name="test-project",
            language="javascript",
            create_claude_hooks=True,
        )

        permissions = init._get_default_permissions()

        # Common permissions
        assert "Bash(git:*)" in permissions

        # JavaScript-specific
        assert "Bash(node:*)" in permissions
        assert "Bash(npm:*)" in permissions
        assert "Bash(yarn:*)" in permissions

        # Should NOT have Python-specific
        assert "Bash(python:*)" not in permissions
        assert "Bash(pytest:*)" not in permissions

    def test_permissions_in_settings_file(self, initializer, temp_project):
        """Test that permissions are written to settings.local.json."""
        initializer._write_claude_settings()

        settings_file = temp_project / ".claude" / "settings.local.json"
        data = json.loads(settings_file.read_text())

        assert "permissions" in data
        assert "allow" in data["permissions"]
        assert len(data["permissions"]["allow"]) > 10  # Should have many permissions
        assert "Bash(git:*)" in data["permissions"]["allow"]


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
        assert (tmp_path / ".claude" / "settings.local.json").exists()

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

    def test_preserve_existing_harness_data(self, tmp_path):
        """Test that reinit preserves existing features.json, config.json, progress.md."""
        harness_dir = tmp_path / ".claude-harness"
        harness_dir.mkdir()

        # Create existing harness data with custom content
        existing_features = {
            "current_phase": "Phase 3",
            "features": [{"id": "F001", "name": "Test Feature", "status": "completed"}],
            "completed": [{"id": "F000", "name": "Done Feature"}],
            "blocked": [],
        }
        (harness_dir / "features.json").write_text(json.dumps(existing_features))

        existing_config = {"project_name": "my-existing-project", "custom_setting": True}
        (harness_dir / "config.json").write_text(json.dumps(existing_config))

        existing_progress = "# My Custom Progress\n\n- Important notes here"
        (harness_dir / "progress.md").write_text(existing_progress)

        # Run initialization
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(project_name="new-project")
        init._generate_files()

        # Verify existing data was preserved (not overwritten)
        features_data = json.loads((harness_dir / "features.json").read_text())
        assert features_data["current_phase"] == "Phase 3"
        assert len(features_data["features"]) == 1
        assert features_data["features"][0]["name"] == "Test Feature"

        config_data = json.loads((harness_dir / "config.json").read_text())
        assert config_data["project_name"] == "my-existing-project"
        assert config_data.get("custom_setting") is True

        progress_content = (harness_dir / "progress.md").read_text()
        assert "My Custom Progress" in progress_content
        assert "Important notes here" in progress_content

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


class TestBuildHarnessSection:
    """Tests for _build_harness_section() and helper methods."""

    def test_build_harness_section_base(self, tmp_path):
        """Test base harness section generation."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            port=5000,
            health_endpoint="/health",
            start_command="python app.py",
            unit_test_command="pytest tests/",
            coverage_threshold=80,
            protected_branches=["main", "master"],
            branch_prefixes=["feat/", "fix/"],
            blocked_actions=["push --force", "rebase -i"],
        )

        section = init._build_harness_section()

        # Check core sections are present
        assert "# CLAUDE HARNESS INTEGRATION" in section
        assert "## MANDATORY BEHAVIORS" in section
        assert "## COMMANDS" in section
        assert "## GIT RULES" in section
        assert "## CONFIG" in section
        assert "## CONTEXT TRACKING" in section

        # Check config values are included
        assert "5000" in section
        assert "/health" in section
        assert "python app.py" in section
        assert "pytest tests/" in section
        assert "80%" in section
        assert "main" in section
        assert "feat/" in section

    def test_build_harness_section_with_delegation(self, tmp_path):
        """Test harness section includes delegation when enabled."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            delegation_enabled=True,
        )

        section = init._build_harness_section()

        assert "## DELEGATION" in section
        assert "Task tool" in section
        assert "explore" in section
        assert "test" in section
        assert "document" in section
        assert "review" in section

    def test_build_harness_section_without_delegation(self, tmp_path):
        """Test harness section excludes delegation when disabled."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            delegation_enabled=False,
        )

        section = init._build_harness_section()

        assert "## DELEGATION" not in section

    def test_build_harness_section_with_orchestration(self, tmp_path):
        """Test harness section includes orchestration when enabled."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            orchestration_enabled=True,
        )

        section = init._build_harness_section()

        assert "## ORCHESTRATION" in section
        assert "orchestrate run" in section
        assert "orchestrate plan" in section
        assert "orchestrate status" in section

    def test_build_harness_section_without_orchestration(self, tmp_path):
        """Test harness section excludes orchestration when disabled."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            orchestration_enabled=False,
        )

        section = init._build_harness_section()

        assert "## ORCHESTRATION" not in section

    def test_build_harness_section_with_discoveries(self, tmp_path):
        """Test harness section includes discoveries when enabled."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            discoveries_enabled=True,
        )

        section = init._build_harness_section()

        assert "## DISCOVERIES" in section
        assert "discovery add" in section
        assert "discovery list" in section
        assert "discovery search" in section

    def test_build_harness_section_without_discoveries(self, tmp_path):
        """Test harness section excludes discoveries when disabled."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            discoveries_enabled=False,
        )

        section = init._build_harness_section()

        assert "## DISCOVERIES" not in section

    def test_build_harness_section_with_e2e(self, tmp_path):
        """Test harness section includes E2E when enabled."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            e2e_enabled=True,
            e2e_test_command="pytest e2e/",
            e2e_base_url="http://localhost:3000",
        )

        section = init._build_harness_section()

        assert "## E2E TESTING" in section
        assert "pytest e2e/" in section
        assert "http://localhost:3000" in section

    def test_build_harness_section_without_e2e(self, tmp_path):
        """Test harness section excludes E2E when disabled."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            e2e_enabled=False,
        )

        section = init._build_harness_section()

        assert "## E2E TESTING" not in section

    def test_build_harness_section_all_features(self, tmp_path):
        """Test harness section with all features enabled."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            delegation_enabled=True,
            orchestration_enabled=True,
            discoveries_enabled=True,
            e2e_enabled=True,
        )

        section = init._build_harness_section()

        # All optional sections should be present
        assert "## DELEGATION" in section
        assert "## ORCHESTRATION" in section
        assert "## DISCOVERIES" in section
        assert "## E2E TESTING" in section

    def test_build_harness_section_token_count(self, tmp_path):
        """Test that compact format is more token-efficient than old format."""
        init = Initializer(str(tmp_path))
        init.config = HarnessConfig(
            project_name="test-project",
            delegation_enabled=True,
        )

        section = init._build_harness_section()

        # Rough token estimate: ~4 chars per token
        estimated_tokens = len(section) / 4

        # Target is ~500-700 tokens for base + delegation + overview
        # Allow margin for overview section (improves agent compliance)
        assert estimated_tokens < 1000, f"Section too large: {estimated_tokens} estimated tokens"


class TestHarnessConfigNewFields:
    """Tests for new config fields: orchestration_enabled, discoveries_enabled."""

    def test_orchestration_enabled_default(self):
        """Test orchestration_enabled defaults to False."""
        config = HarnessConfig()
        assert config.orchestration_enabled is False

    def test_discoveries_enabled_default(self):
        """Test discoveries_enabled defaults to False."""
        config = HarnessConfig()
        assert config.discoveries_enabled is False

    def test_orchestration_enabled_custom(self):
        """Test orchestration_enabled can be set."""
        config = HarnessConfig(orchestration_enabled=True)
        assert config.orchestration_enabled is True

    def test_discoveries_enabled_custom(self):
        """Test discoveries_enabled can be set."""
        config = HarnessConfig(discoveries_enabled=True)
        assert config.discoveries_enabled is True

    def test_to_dict_includes_orchestration(self):
        """Test to_dict includes orchestration section."""
        config = HarnessConfig(orchestration_enabled=True)
        data = config.to_dict()

        assert "orchestration" in data
        assert data["orchestration"]["enabled"] is True

    def test_to_dict_includes_discoveries(self):
        """Test to_dict includes discoveries section."""
        config = HarnessConfig(discoveries_enabled=True)
        data = config.to_dict()

        assert "discoveries" in data
        assert data["discoveries"]["enabled"] is True

    def test_to_dict_orchestration_disabled(self):
        """Test to_dict with orchestration disabled."""
        config = HarnessConfig(orchestration_enabled=False)
        data = config.to_dict()

        assert "orchestration" in data
        assert data["orchestration"]["enabled"] is False

    def test_to_dict_discoveries_disabled(self):
        """Test to_dict with discoveries disabled."""
        config = HarnessConfig(discoveries_enabled=False)
        data = config.to_dict()

        assert "discoveries" in data
        assert data["discoveries"]["enabled"] is False


class TestCheckSubtasksHook:
    """Tests for the check-subtasks.sh session end hook."""

    def test_check_subtasks_hook_created(self, tmp_path):
        """Test that check-subtasks.sh hook is created during init."""
        initializer = Initializer(str(tmp_path), non_interactive=True)
        initializer.run()

        hook_path = tmp_path / ".claude-harness" / "hooks" / "check-subtasks.sh"
        assert hook_path.exists()

    def test_check_subtasks_hook_executable(self, tmp_path):
        """Test that check-subtasks.sh hook is executable."""
        initializer = Initializer(str(tmp_path), non_interactive=True)
        initializer.run()

        hook_path = tmp_path / ".claude-harness" / "hooks" / "check-subtasks.sh"
        import os
        assert os.access(hook_path, os.X_OK)

    def test_check_subtasks_hook_content(self, tmp_path):
        """Test check-subtasks.sh hook contains expected elements."""
        initializer = Initializer(str(tmp_path), non_interactive=True)
        initializer.run()

        hook_path = tmp_path / ".claude-harness" / "hooks" / "check-subtasks.sh"
        content = hook_path.read_text()

        # Check key elements
        assert "#!/bin/bash" in content
        assert "Subtask Audit Hook" in content
        assert "features.json" in content
        assert "in_progress" in content
        assert "SUBTASK REMINDER" in content
        assert "feature done" in content

    def test_check_subtasks_registered_in_settings(self, tmp_path):
        """Test check-subtasks.sh is registered in SessionEnd hooks."""
        initializer = Initializer(str(tmp_path), non_interactive=True)
        initializer.run()

        settings_path = tmp_path / ".claude" / "settings.local.json"
        settings = json.loads(settings_path.read_text())

        # Find check-subtasks in SessionEnd hooks
        session_end_hooks = settings.get("hooks", {}).get("SessionEnd", [])
        hook_commands = []
        for entry in session_end_hooks:
            for hook in entry.get("hooks", []):
                hook_commands.append(hook.get("command", ""))

        assert ".claude-harness/hooks/check-subtasks.sh" in hook_commands

    def test_check_subtasks_runs_before_session_stop(self, tmp_path):
        """Test check-subtasks.sh runs before session-stop.sh."""
        initializer = Initializer(str(tmp_path), non_interactive=True)
        initializer.run()

        settings_path = tmp_path / ".claude" / "settings.local.json"
        settings = json.loads(settings_path.read_text())

        session_end_hooks = settings.get("hooks", {}).get("SessionEnd", [])
        hook_commands = []
        for entry in session_end_hooks:
            for hook in entry.get("hooks", []):
                hook_commands.append(hook.get("command", ""))

        # check-subtasks should come before session-stop
        check_idx = hook_commands.index(".claude-harness/hooks/check-subtasks.sh")
        stop_idx = hook_commands.index(".claude-harness/hooks/session-stop.sh")
        assert check_idx < stop_idx, "check-subtasks should run before session-stop"
