"""Tests for env file loading (env_file / env_files references)."""

from ccpm.core.compiler import compile_profile


class TestEnvFileLoading:
    def test_loads_from_env_file(self, search_path):
        compiled = compile_profile("with-env-file", search_path)
        assert compiled.env["ANTHROPIC_API_KEY"] == "sk-ant-example-key-not-real"
        assert compiled.env["GITHUB_TOKEN"] == "ghp_example_token_not_real"
        assert compiled.env["CUSTOM_SETTING"] == "from-env-file"

    def test_quoted_values(self, search_path):
        compiled = compile_profile("with-env-file", search_path)
        assert compiled.env["DATABASE_URL"] == "postgresql://localhost:5432/mydb"

    def test_export_prefix_stripped(self, search_path):
        compiled = compile_profile("with-env-file", search_path)
        assert compiled.env["ANOTHER_VAR"] == "exported-value"

    def test_inline_vars_merge_on_top(self, search_path):
        compiled = compile_profile("with-env-file", search_path)
        assert compiled.env["EXTRA_VAR"] == "inline-value"

    def test_inline_vars_override_file(self, tmp_path):
        """Inline env vars should override file-loaded vars."""
        env_file = tmp_path / ".env"
        env_file.write_text("KEY=from-file\n")
        profile = tmp_path / "test.toml"
        profile.write_text(f'''
[profile]
name = "test"

[env]
env_file = ".env"
KEY = "from-inline"
''')
        compiled = compile_profile(str(profile), [])
        assert compiled.env["KEY"] == "from-inline"

    def test_multiple_env_files(self, tmp_path):
        """env_files loads multiple files, later overriding earlier."""
        (tmp_path / "defaults.env").write_text("A=1\nB=2\n")
        (tmp_path / "local.env").write_text("B=overridden\nC=3\n")
        profile = tmp_path / "test.toml"
        profile.write_text('''
[profile]
name = "test"

[env]
env_files = ["defaults.env", "local.env"]
''')
        compiled = compile_profile(str(profile), [])
        assert compiled.env["A"] == "1"
        assert compiled.env["B"] == "overridden"
        assert compiled.env["C"] == "3"

    def test_missing_env_file_raises(self, tmp_path):
        import pytest

        profile = tmp_path / "test.toml"
        profile.write_text('''
[profile]
name = "test"

[env]
env_file = "nonexistent.env"
''')
        with pytest.raises(FileNotFoundError):
            compile_profile(str(profile), [])

    def test_comments_and_blank_lines_skipped(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# comment\n\nKEY=val\n  # indented comment\n\n")
        profile = tmp_path / "test.toml"
        profile.write_text('''
[profile]
name = "test"

[env]
env_file = ".env"
''')
        compiled = compile_profile(str(profile), [])
        assert compiled.env == {"KEY": "val"}

    def test_cli_var_used_in_expansion(self, tmp_path):
        """CLI --var overrides are used for ${VAR} expansion in env values."""
        env_file = tmp_path / ".env"
        env_file.write_text("BASE_URL=http://default\n")
        profile = tmp_path / "test.toml"
        profile.write_text('''
[profile]
name = "test"

[env]
env_file = ".env"
API_URL = "${MY_HOST:-localhost}:8080"
''')
        compiled = compile_profile(str(profile), [], env_overrides={"MY_HOST": "custom.host"})
        assert compiled.env["API_URL"] == "custom.host:8080"
        assert compiled.env["BASE_URL"] == "http://default"
