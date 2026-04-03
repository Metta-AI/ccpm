"""Tests for credential resolution."""

import os

import pytest

from ccpm.core.compiler import MissingCredential, compile_profile


class TestCredentialFromEnv:
    def test_resolve_from_env(self, search_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp-test-token")
        compiled = compile_profile("with-credentials", search_path)
        assert compiled.env["ANTHROPIC_API_KEY"] == "sk-test-key"
        assert compiled.env["GITHUB_TOKEN"] == "ghp-test-token"

    def test_resolve_from_cli_override(self, search_path, monkeypatch):
        # Ensure not in env
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        compiled = compile_profile(
            "with-credentials",
            search_path,
            env_overrides={
                "ANTHROPIC_API_KEY": "override-key",
                "GITHUB_TOKEN": "override-token",
            },
        )
        assert compiled.env["ANTHROPIC_API_KEY"] == "override-key"
        assert compiled.env["GITHUB_TOKEN"] == "override-token"

    def test_cli_override_beats_env(self, search_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "env-key")
        monkeypatch.setenv("GITHUB_TOKEN", "env-token")
        compiled = compile_profile(
            "with-credentials",
            search_path,
            env_overrides={"ANTHROPIC_API_KEY": "override-key", "GITHUB_TOKEN": "x"},
        )
        assert compiled.env["ANTHROPIC_API_KEY"] == "override-key"


class TestCredentialRequired:
    def test_missing_required_raises(self, search_path, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(MissingCredential) as exc_info:
            compile_profile("with-credentials", search_path)
        assert "ANTHROPIC_API_KEY" in str(exc_info.value)


class TestCredentialOptional:
    def test_optional_skipped_when_missing(self, search_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        monkeypatch.setenv("GITHUB_TOKEN", "token")
        monkeypatch.delenv("SENTRY_DSN", raising=False)
        compiled = compile_profile("with-credentials", search_path)
        # Optional SENTRY_DSN not in env, should not be in output
        assert "SENTRY_DSN" not in compiled.env

    def test_optional_included_when_present(self, search_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        monkeypatch.setenv("GITHUB_TOKEN", "token")
        monkeypatch.setenv("SENTRY_DSN", "https://sentry.example.com/1")
        compiled = compile_profile("with-credentials", search_path)
        assert compiled.env["SENTRY_DSN"] == "https://sentry.example.com/1"


class TestCredentialSourceCommand:
    def test_source_command_fallback(self, search_path, tmp_path, monkeypatch):
        """When env var is missing, source command runs."""
        monkeypatch.delenv("MY_SECRET", raising=False)
        # Create a profile with a source command that echoes a value
        profile = tmp_path / "cmd-cred.toml"
        profile.write_text('''
[profile]
name = "cmd-cred"
description = "test"

[[credentials]]
name = "my-secret"
env_var = "MY_SECRET"
description = "test secret"
source = "echo test-secret-value"
''')
        compiled = compile_profile(str(profile), [])
        assert compiled.env["MY_SECRET"] == "test-secret-value"

    def test_source_command_not_used_when_env_set(self, search_path, tmp_path, monkeypatch):
        """Env var takes priority over source command."""
        monkeypatch.setenv("MY_SECRET", "from-env")
        profile = tmp_path / "cmd-cred.toml"
        profile.write_text('''
[profile]
name = "cmd-cred"
description = "test"

[[credentials]]
name = "my-secret"
env_var = "MY_SECRET"
source = "echo should-not-run"
''')
        compiled = compile_profile(str(profile), [])
        assert compiled.env["MY_SECRET"] == "from-env"

    def test_failed_source_command_raises(self, tmp_path, monkeypatch):
        """Failed source command for required credential raises."""
        monkeypatch.delenv("MY_SECRET", raising=False)
        profile = tmp_path / "cmd-cred.toml"
        profile.write_text('''
[profile]
name = "cmd-cred"
description = "test"

[[credentials]]
name = "my-secret"
env_var = "MY_SECRET"
description = "test secret"
source = "exit 1"
''')
        with pytest.raises(MissingCredential):
            compile_profile(str(profile), [])


class TestCredentialsMergeWithEnv:
    def test_credentials_appear_in_env_output(self, search_path, tmp_path, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "key")
        monkeypatch.setenv("GITHUB_TOKEN", "token")
        compiled = compile_profile("with-credentials", search_path)
        # Credentials should be in the env dict alongside regular env vars
        assert "ANTHROPIC_API_KEY" in compiled.env
        assert "GITHUB_TOKEN" in compiled.env

    def test_credentials_in_emitted_env_file(self, search_path, tmp_path, monkeypatch):
        from ccpm.emit import emit_all

        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp-test")
        compiled = compile_profile("with-credentials", search_path)
        emit_all(compiled, tmp_path / "out")
        env_text = (tmp_path / "out" / ".env.claude").read_text()
        assert 'ANTHROPIC_API_KEY' in env_text
        assert 'GITHUB_TOKEN' in env_text
