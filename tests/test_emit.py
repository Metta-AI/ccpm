"""Tests for emitters — settings.json, CLAUDE.md, .mcp.json, files, .env.claude."""

import json

import pytest

from ccpm.core.compiler import compile_profile
from ccpm.emit import emit_all
from ccpm.emit.claude_md import emit_claude_md
from ccpm.emit.env_file import emit_env_file
from ccpm.emit.mcp import emit_mcp
from ccpm.emit.settings import emit_settings


class TestEmitSettings:
    def test_writes_settings_json(self, tmp_output):
        settings = {"model": "opus", "permissions": {"allow": ["Read"]}}
        path = emit_settings(settings, tmp_output)
        assert path is not None
        assert path.name == "settings.json"
        data = json.loads(path.read_text())
        assert data["model"] == "opus"

    def test_settings_location(self, tmp_output):
        path = emit_settings({"model": "opus"}, tmp_output)
        assert path == tmp_output / ".claude" / "settings.json"

    def test_empty_settings_returns_none(self, tmp_output):
        assert emit_settings({}, tmp_output) is None

    def test_hooks_transformed(self, tmp_output):
        """Hooks in intermediate format should be converted to Claude Code format."""
        settings = {
            "hooks": {
                "PostToolUse": [
                    {"matcher": "Edit|Write", "commands": ["format.sh", "lint.sh"]}
                ],
                "SessionStart": [{"commands": ["echo hello"]}],
            }
        }
        path = emit_settings(settings, tmp_output)
        data = json.loads(path.read_text())
        # PostToolUse
        post = data["hooks"]["PostToolUse"][0]
        assert post["matcher"] == "Edit|Write"
        assert post["hooks"] == [
            {"type": "command", "command": "format.sh"},
            {"type": "command", "command": "lint.sh"},
        ]
        # SessionStart
        start = data["hooks"]["SessionStart"][0]
        assert "matcher" not in start
        assert start["hooks"] == [{"type": "command", "command": "echo hello"}]

    def test_plugins_passthrough(self, tmp_output):
        settings = {"enabledPlugins": {"my-plugin@market": True}}
        path = emit_settings(settings, tmp_output)
        data = json.loads(path.read_text())
        assert data["enabledPlugins"]["my-plugin@market"] is True


class TestEmitClaudeMd:
    def test_append_strategy(self, tmp_output):
        entries = [
            {"strategy": "append", "content": "First"},
            {"strategy": "append", "content": "Second"},
        ]
        path = emit_claude_md(entries, tmp_output)
        text = path.read_text()
        assert "First" in text
        assert "Second" in text
        assert text.index("First") < text.index("Second")

    def test_prepend_strategy(self, tmp_output):
        entries = [
            {"strategy": "append", "content": "First"},
            {"strategy": "prepend", "content": "Before"},
        ]
        path = emit_claude_md(entries, tmp_output)
        text = path.read_text()
        assert text.index("Before") < text.index("First")

    def test_replace_strategy(self, tmp_output):
        entries = [
            {"strategy": "append", "content": "First"},
            {"strategy": "replace", "content": "Only This"},
        ]
        path = emit_claude_md(entries, tmp_output)
        text = path.read_text()
        assert "First" not in text
        assert "Only This" in text

    def test_file_reference(self, tmp_output, examples_dir):
        entries = [{"strategy": "replace", "file": str(examples_dir / "claude-md-sample.md")}]
        path = emit_claude_md(entries, tmp_output)
        text = path.read_text()
        assert "Sample CLAUDE.md" in text

    def test_empty_returns_none(self, tmp_output):
        assert emit_claude_md([], tmp_output) is None

    def test_location(self, tmp_output):
        path = emit_claude_md([{"strategy": "append", "content": "Hi"}], tmp_output)
        assert path == tmp_output / "CLAUDE.md"

    def test_missing_file_ref_raises(self, tmp_output):
        entries = [{"strategy": "replace", "file": "/nonexistent/path.md"}]
        with pytest.raises(FileNotFoundError):
            emit_claude_md(entries, tmp_output)


class TestEmitMcp:
    def test_writes_mcp_json(self, tmp_output):
        servers = {
            "github": {"name": "github", "command": "gh", "args": ["mcp"]},
        }
        path = emit_mcp(servers, tmp_output)
        data = json.loads(path.read_text())
        assert "github" in data
        assert data["github"]["command"] == "gh"
        # 'name' should not be in the output (it becomes the key)
        assert "name" not in data["github"]

    def test_multiple_servers(self, tmp_output):
        servers = {
            "github": {"name": "github", "command": "gh", "args": ["mcp"]},
            "api": {"name": "api", "type": "http", "url": "http://localhost:8080"},
        }
        path = emit_mcp(servers, tmp_output)
        data = json.loads(path.read_text())
        assert len(data) == 2
        assert data["api"]["type"] == "http"

    def test_empty_returns_none(self, tmp_output):
        assert emit_mcp({}, tmp_output) is None

    def test_location(self, tmp_output):
        path = emit_mcp({"x": {"name": "x", "command": "x"}}, tmp_output)
        assert path == tmp_output / ".mcp.json"


class TestEmitEnvFile:
    def test_writes_env_file(self, tmp_output):
        path = emit_env_file({"KEY": "val", "OTHER": "123"}, tmp_output)
        text = path.read_text()
        assert 'export KEY="val"' in text
        assert 'export OTHER="123"' in text

    def test_sorted_output(self, tmp_output):
        path = emit_env_file({"ZZZ": "1", "AAA": "2"}, tmp_output)
        text = path.read_text()
        assert text.index("AAA") < text.index("ZZZ")

    def test_empty_returns_none(self, tmp_output):
        assert emit_env_file({}, tmp_output) is None

    def test_location(self, tmp_output):
        path = emit_env_file({"K": "V"}, tmp_output)
        assert path == tmp_output / ".env.claude"


class TestEmitAll:
    def test_full_featured_profile(self, search_path, tmp_output, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        written = emit_all(compiled, tmp_output)
        paths = {p.relative_to(tmp_output).as_posix() for p in written}

        assert ".claude/settings.json" in paths
        assert "CLAUDE.md" in paths
        assert ".mcp.json" in paths
        assert ".env.claude" in paths
        # File assets
        assert ".claude/skills/my-skill" in paths or any("my-skill" in p for p in paths)
        assert any("todo.md" in p for p in paths)
        assert any("reviewer.md" in p for p in paths)
        assert any("session-start.sh" in p for p in paths)

    def test_settings_json_valid(self, search_path, tmp_output, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        emit_all(compiled, tmp_output)
        settings = json.loads((tmp_output / ".claude" / "settings.json").read_text())
        assert "permissions" in settings
        assert "hooks" in settings
        assert "enabledPlugins" in settings

    def test_skill_directory_copied(self, search_path, tmp_output, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        emit_all(compiled, tmp_output)
        skill_md = tmp_output / ".claude" / "skills" / "my-skill" / "SKILL.md"
        assert skill_md.is_file()
        assert "Example skill" in skill_md.read_text()

    def test_command_file_copied(self, search_path, tmp_output, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        emit_all(compiled, tmp_output)
        cmd = tmp_output / ".claude" / "commands" / "todo.md"
        assert cmd.is_file()
        assert "Todo Management" in cmd.read_text()

    def test_minimal_profile_output(self, search_path, tmp_output):
        compiled = compile_profile("minimal", search_path)
        written = emit_all(compiled, tmp_output)
        # Only settings.json should be written
        assert len(written) == 1
        assert written[0].name == "settings.json"
