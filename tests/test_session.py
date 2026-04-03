"""Tests for session log deployment."""

import json

import pytest

from ccpm.core.compiler import compile_profile
from ccpm.emit import emit_all
from ccpm.emit.session import (
    DEFAULT_WARNING,
    _extract_cwd,
    _extract_session_id,
    emit_session,
    project_dir_hash,
)


class TestProjectDirHash:
    def test_simple_path(self):
        assert project_dir_hash("/home/user") == "-home-user"

    def test_root(self):
        assert project_dir_hash("/") == "-"

    def test_nested_path(self):
        assert project_dir_hash("/Users/kyle/git/ccpm") == "-Users-kyle-git-ccpm"


class TestExtractSessionId:
    def test_extracts_from_first_entry(self, examples_dir):
        log = examples_dir / "sessions" / "example-session.jsonl"
        assert _extract_session_id(log) == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def test_falls_back_to_filename(self, tmp_path):
        log = tmp_path / "my-session.jsonl"
        log.write_text("{}\n")
        assert _extract_session_id(log) == "my-session"


class TestExtractCwd:
    def test_extracts_cwd(self, examples_dir):
        log = examples_dir / "sessions" / "example-session.jsonl"
        assert _extract_cwd(log) == "/home/user/my-project"

    def test_returns_none_when_missing(self, tmp_path):
        log = tmp_path / "empty.jsonl"
        log.write_text('{"type": "permission-mode"}\n')
        assert _extract_cwd(log) is None


class TestEmitSession:
    def test_copies_session_log(self, tmp_path, examples_dir):
        config = {
            "_resolved_log": str(examples_dir / "sessions" / "example-session.jsonl"),
        }
        written = emit_session(config, tmp_path)
        # Should have session file + resume script
        assert len(written) >= 2
        session_files = [p for p in written if p.suffix == ".jsonl"]
        assert len(session_files) == 1
        assert session_files[0].exists()

    def test_injects_default_warning(self, tmp_path, examples_dir):
        config = {
            "_resolved_log": str(examples_dir / "sessions" / "example-session.jsonl"),
        }
        written = emit_session(config, tmp_path)
        session_file = [p for p in written if p.suffix == ".jsonl"][0]
        lines = session_file.read_text().strip().split("\n")
        last_entry = json.loads(lines[-1])
        assert last_entry["type"] == "summary"
        assert "WARNING TO CLAUDE" in last_entry["summary"]
        assert "incompatible environment" in last_entry["summary"]

    def test_custom_warning(self, tmp_path, examples_dir):
        config = {
            "_resolved_log": str(examples_dir / "sessions" / "example-session.jsonl"),
            "warning": "You are now in a Docker container.",
        }
        written = emit_session(config, tmp_path)
        session_file = [p for p in written if p.suffix == ".jsonl"][0]
        lines = session_file.read_text().strip().split("\n")
        last_entry = json.loads(lines[-1])
        assert last_entry["summary"] == "You are now in a Docker container."

    def test_session_placed_in_correct_project_dir(self, tmp_path, examples_dir):
        config = {
            "_resolved_log": str(examples_dir / "sessions" / "example-session.jsonl"),
        }
        emit_session(config, tmp_path)
        # cwd in the example session is /home/user/my-project
        expected_dir = tmp_path / ".claude" / "projects" / "-home-user-my-project"
        assert expected_dir.is_dir()
        jsonl_files = list(expected_dir.glob("*.jsonl"))
        assert len(jsonl_files) == 1
        assert jsonl_files[0].name == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee.jsonl"

    def test_custom_project_dir(self, tmp_path, examples_dir):
        config = {
            "_resolved_log": str(examples_dir / "sessions" / "example-session.jsonl"),
            "project_dir": "/workspace/code",
        }
        emit_session(config, tmp_path)
        expected_dir = tmp_path / ".claude" / "projects" / "-workspace-code"
        assert expected_dir.is_dir()

    def test_target_cwd_overrides_project_dir(self, tmp_path, examples_dir):
        config = {
            "_resolved_log": str(examples_dir / "sessions" / "example-session.jsonl"),
            "project_dir": "/should/not/use",
        }
        emit_session(config, tmp_path, target_cwd="/actual/target")
        expected_dir = tmp_path / ".claude" / "projects" / "-actual-target"
        assert expected_dir.is_dir()

    def test_generates_resume_script(self, tmp_path, examples_dir):
        config = {
            "_resolved_log": str(examples_dir / "sessions" / "example-session.jsonl"),
        }
        written = emit_session(config, tmp_path)
        resume_scripts = [p for p in written if p.name == "ccpm-resume.sh"]
        assert len(resume_scripts) == 1
        text = resume_scripts[0].read_text()
        assert "claude --resume aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee" in text
        # Should be executable
        import stat
        assert resume_scripts[0].stat().st_mode & stat.S_IXUSR

    def test_preserves_original_entries(self, tmp_path, examples_dir):
        config = {
            "_resolved_log": str(examples_dir / "sessions" / "example-session.jsonl"),
        }
        written = emit_session(config, tmp_path)
        session_file = [p for p in written if p.suffix == ".jsonl"][0]
        lines = session_file.read_text().strip().split("\n")
        # Original has 5 entries, we add 1 warning
        assert len(lines) == 6
        # First entry should be permission-mode
        first = json.loads(lines[0])
        assert first["type"] == "permission-mode"
        # Third entry should be the user message
        third = json.loads(lines[2])
        assert third["type"] == "user"
        assert "CI pipeline" in third["message"]["content"]

    def test_none_config_returns_empty(self, tmp_path):
        assert emit_session(None, tmp_path) == []

    def test_missing_log_raises(self, tmp_path):
        config = {"_resolved_log": str(tmp_path / "nonexistent.jsonl")}
        with pytest.raises(FileNotFoundError):
            emit_session(config, tmp_path / "out")


class TestSessionInProfile:
    def test_session_from_toml_profile(self, search_path, tmp_path):
        compiled = compile_profile("with-session", search_path)
        assert compiled.session is not None
        assert "_resolved_log" in compiled.session

    def test_session_emitted_in_build(self, search_path, tmp_path):
        compiled = compile_profile("with-session", search_path)
        written = emit_all(compiled, tmp_path / "out")
        names = {p.name for p in written}
        assert "ccpm-resume.sh" in names
        jsonl_files = [p for p in written if p.suffix == ".jsonl"]
        assert len(jsonl_files) == 1

    def test_cli_session_override(self, search_path, tmp_path, examples_dir):
        session_path = str(examples_dir / "sessions" / "example-session.jsonl")
        compiled = compile_profile(
            "base-readonly", search_path, session_log=session_path
        )
        assert compiled.session is not None
        assert compiled.session["_resolved_log"] == session_path

    def test_cli_session_overrides_toml_session(self, search_path, tmp_path, examples_dir):
        other_session = tmp_path / "other.jsonl"
        other_session.write_text(
            '{"type": "permission-mode", "permissionMode": "default", "sessionId": "override-id"}\n'
            '{"type": "user", "message": {"role": "user", "content": "hi"}, "cwd": "/other", "sessionId": "override-id"}\n'
        )
        compiled = compile_profile(
            "with-session", search_path, session_log=str(other_session)
        )
        written = emit_all(compiled, tmp_path / "out")
        jsonl_files = [p for p in written if p.suffix == ".jsonl"]
        assert len(jsonl_files) == 1
        assert "override-id" in jsonl_files[0].name

    def test_session_with_support_dir(self, tmp_path, examples_dir):
        """If the session has a supporting directory (subagents, tool-results), copy it."""
        # Create a session with a support directory
        session_dir = tmp_path / "sessions"
        session_dir.mkdir()
        session_id = "test-session-with-dir"
        log = session_dir / f"{session_id}.jsonl"
        log.write_text(
            f'{{"type": "permission-mode", "sessionId": "{session_id}"}}\n'
            f'{{"type": "user", "message": {{"role": "user", "content": "hi"}}, "cwd": "/test", "sessionId": "{session_id}"}}\n'
        )
        # Create support directory
        support = session_dir / session_id
        support.mkdir()
        (support / "subagents").mkdir()
        (support / "subagents" / "agent1.jsonl").write_text("{}\n")

        config = {"_resolved_log": str(log)}
        written = emit_session(config, tmp_path / "out")
        dest_support = tmp_path / "out" / ".claude" / "projects" / "-test" / session_id
        assert dest_support.is_dir()
        assert (dest_support / "subagents" / "agent1.jsonl").exists()
