"""Tests for command_generator.py - Claude Code slash command generation."""

import pytest
from pathlib import Path

from claude_harness.command_generator import (
    HARNESS_COMMANDS,
    generate_command_file,
    write_commands_to_directory,
    get_command_list,
    generate_commands_readme,
)


class TestHarnessCommands:
    """Tests for HARNESS_COMMANDS constant."""

    def test_commands_exist(self):
        """Test that commands dictionary is populated."""
        assert len(HARNESS_COMMANDS) > 0

    def test_commands_have_required_fields(self):
        """Test that all commands have required fields."""
        for name, cmd_data in HARNESS_COMMANDS.items():
            assert "description" in cmd_data, f"{name} missing description"
            assert "content" in cmd_data, f"{name} missing content"
            assert len(cmd_data["description"]) > 0, f"{name} has empty description"
            assert len(cmd_data["content"]) > 0, f"{name} has empty content"

    def test_core_commands_present(self):
        """Test that core commands are defined."""
        expected_commands = [
            "harness-init",
            "harness-status",
            "harness-feature-list",
            "harness-feature-add",
            "harness-feature-start",
            "harness-feature-complete",
            "harness-progress",
            "harness-context",
            "harness-delegation-status",
            "harness-delegation-suggest",
        ]
        for cmd in expected_commands:
            assert cmd in HARNESS_COMMANDS, f"Missing core command: {cmd}"

    def test_feature_commands_present(self):
        """Test that all feature management commands are defined."""
        feature_commands = [
            "harness-feature-list",
            "harness-feature-add",
            "harness-feature-start",
            "harness-feature-complete",
            "harness-feature-block",
            "harness-feature-unblock",
            "harness-feature-done",
            "harness-feature-info",
            "harness-feature-note",
            "harness-feature-tests",
        ]
        for cmd in feature_commands:
            assert cmd in HARNESS_COMMANDS, f"Missing feature command: {cmd}"

    def test_delegation_commands_present(self):
        """Test that delegation commands are defined."""
        delegation_commands = [
            "harness-delegation-status",
            "harness-delegation-enable",
            "harness-delegation-disable",
            "harness-delegation-rules",
            "harness-delegation-suggest",
            "harness-delegation-auto",
            "harness-delegation-add-rule",
        ]
        for cmd in delegation_commands:
            assert cmd in HARNESS_COMMANDS, f"Missing delegation command: {cmd}"

    def test_progress_commands_present(self):
        """Test that progress commands are defined."""
        progress_commands = [
            "harness-progress",
            "harness-progress-completed",
            "harness-progress-wip",
            "harness-progress-blocker",
            "harness-progress-file",
            "harness-progress-new-session",
            "harness-progress-history",
        ]
        for cmd in progress_commands:
            assert cmd in HARNESS_COMMANDS, f"Missing progress command: {cmd}"

    def test_context_commands_present(self):
        """Test that context commands are defined."""
        context_commands = [
            "harness-context",
            "harness-context-summary",
            "harness-context-handoff",
            "harness-context-compress",
        ]
        for cmd in context_commands:
            assert cmd in HARNESS_COMMANDS, f"Missing context command: {cmd}"


class TestGenerateCommandFile:
    """Tests for generate_command_file function."""

    def test_basic_generation(self):
        """Test basic command file generation."""
        content = generate_command_file(
            name="test-cmd",
            description="A test command",
            content="Run this test command."
        )
        assert "Run this test command." in content

    def test_content_preserved(self):
        """Test that content is preserved in output."""
        original_content = """This is a multi-line
command content with
special characters: $ARGUMENTS"""

        result = generate_command_file(
            name="test",
            description="test",
            content=original_content
        )
        assert original_content in result


class TestWriteCommandsToDirectory:
    """Tests for write_commands_to_directory function."""

    def test_creates_command_files(self, tmp_path):
        """Test that command files are created."""
        commands_dir = tmp_path / "commands"

        created = write_commands_to_directory(commands_dir)

        assert len(created) > 0
        assert commands_dir.exists()

    def test_creates_all_commands(self, tmp_path):
        """Test that all commands are created."""
        commands_dir = tmp_path / "commands"

        created = write_commands_to_directory(commands_dir)

        assert len(created) == len(HARNESS_COMMANDS)

    def test_command_files_have_md_extension(self, tmp_path):
        """Test that command files have .md extension."""
        commands_dir = tmp_path / "commands"

        write_commands_to_directory(commands_dir)

        for cmd_name in HARNESS_COMMANDS:
            file_path = commands_dir / f"{cmd_name}.md"
            assert file_path.exists(), f"Missing file: {cmd_name}.md"

    def test_command_files_have_content(self, tmp_path):
        """Test that command files have content."""
        commands_dir = tmp_path / "commands"

        write_commands_to_directory(commands_dir)

        for cmd_name, cmd_data in HARNESS_COMMANDS.items():
            file_path = commands_dir / f"{cmd_name}.md"
            content = file_path.read_text()
            assert len(content) > 0
            # Content should include the command content
            assert cmd_data["content"].strip()[:50] in content

    def test_custom_commands_dict(self, tmp_path):
        """Test with custom commands dictionary."""
        commands_dir = tmp_path / "commands"
        custom_commands = {
            "custom-cmd": {
                "description": "Custom command",
                "content": "Custom content here."
            }
        }

        created = write_commands_to_directory(commands_dir, custom_commands)

        assert len(created) == 1
        assert (commands_dir / "custom-cmd.md").exists()

    def test_overwrites_existing(self, tmp_path):
        """Test that existing files are overwritten."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        # Create an existing file
        (commands_dir / "harness-status.md").write_text("old content")

        write_commands_to_directory(commands_dir)

        content = (commands_dir / "harness-status.md").read_text()
        assert "old content" not in content


class TestGetCommandList:
    """Tests for get_command_list function."""

    def test_returns_list(self):
        """Test that function returns a list."""
        result = get_command_list()
        assert isinstance(result, list)

    def test_list_length_matches_commands(self):
        """Test that list length matches HARNESS_COMMANDS."""
        result = get_command_list()
        assert len(result) == len(HARNESS_COMMANDS)

    def test_entries_have_name_and_description(self):
        """Test that each entry has name and description."""
        result = get_command_list()
        for entry in result:
            assert "name" in entry
            assert "description" in entry

    def test_names_start_with_slash(self):
        """Test that command names start with /."""
        result = get_command_list()
        for entry in result:
            assert entry["name"].startswith("/"), f"{entry['name']} doesn't start with /"


class TestGenerateCommandsReadme:
    """Tests for generate_commands_readme function."""

    def test_creates_readme(self, tmp_path):
        """Test that README is created."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        readme_path = generate_commands_readme(commands_dir)

        assert Path(readme_path).exists()
        assert Path(readme_path).name == "README.md"

    def test_readme_has_title(self, tmp_path):
        """Test that README has title."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        readme_path = generate_commands_readme(commands_dir)
        content = Path(readme_path).read_text()

        assert "# Claude Harness Commands" in content

    def test_readme_lists_commands(self, tmp_path):
        """Test that README lists commands."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        readme_path = generate_commands_readme(commands_dir)
        content = Path(readme_path).read_text()

        # Should have a table with commands
        assert "/harness-status" in content
        assert "/harness-feature-add" in content

    def test_readme_has_usage_section(self, tmp_path):
        """Test that README has usage section."""
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()

        readme_path = generate_commands_readme(commands_dir)
        content = Path(readme_path).read_text()

        assert "## Usage" in content


class TestCommandContent:
    """Tests for specific command content."""

    def test_init_command_detects_stack(self):
        """Test that init command includes stack detection."""
        content = HARNESS_COMMANDS["harness-init"]["content"]
        assert "detect" in content.lower()

    def test_feature_add_asks_questions(self):
        """Test that feature add asks for required info."""
        content = HARNESS_COMMANDS["harness-feature-add"]["content"]
        assert "feature name" in content.lower() or "subtask" in content.lower()

    def test_delegation_suggest_shows_savings(self):
        """Test that delegation suggest mentions savings."""
        content = HARNESS_COMMANDS["harness-delegation-suggest"]["content"]
        assert "saving" in content.lower() or "token" in content.lower()

    def test_context_handoff_creates_document(self):
        """Test that context handoff mentions document creation."""
        content = HARNESS_COMMANDS["harness-context-handoff"]["content"]
        assert "handoff" in content.lower()

    def test_commands_use_arguments_placeholder(self):
        """Test that commands with args use $ARGUMENTS."""
        commands_with_args = [
            "harness-feature-add",
            "harness-feature-start",
            "harness-feature-done",
            "harness-delegation-suggest",
        ]
        for cmd_name in commands_with_args:
            content = HARNESS_COMMANDS[cmd_name]["content"]
            assert "$ARGUMENTS" in content, f"{cmd_name} should use $ARGUMENTS"
