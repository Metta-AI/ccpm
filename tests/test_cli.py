"""Tests for the CLI commands."""

import json

from click.testing import CliRunner

from ccpm.cli import main


class TestBuild:
    def test_build_minimal(self, profiles_dir, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "build", "minimal", "-o", str(tmp_path / "out")],
        )
        assert result.exit_code == 0
        assert "1 files" in result.output
        assert (tmp_path / "out" / ".claude" / "settings.json").is_file()

    def test_build_chain(self, profiles_dir, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "build", "python-dev", "-o", str(tmp_path / "out")],
        )
        assert result.exit_code == 0
        # Chain may wrap across lines in terminal output
        assert "base-readonly" in result.output
        assert "python-dev" in result.output

    def test_build_verbose(self, profiles_dir, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "build", "python-dev", "-v", "-o", str(tmp_path / "out")],
        )
        assert result.exit_code == 0
        assert "Step 1" in result.output or "merged" in result.output

    def test_build_with_env_var(self, profiles_dir, examples_dir, tmp_path):
        runner = CliRunner()
        result = runner.invoke(
            main,
            [
                "--profile-path", str(profiles_dir),
                "build", "full-featured",
                "--var", f"EXAMPLES_DIR={examples_dir}",
                "-o", str(tmp_path / "out"),
            ],
        )
        assert result.exit_code == 0
        assert (tmp_path / "out" / ".claude" / "settings.json").is_file()
        assert (tmp_path / "out" / "CLAUDE.md").is_file()
        assert (tmp_path / "out" / ".mcp.json").is_file()


class TestList:
    def test_list_profiles(self, profiles_dir):
        runner = CliRunner()
        result = runner.invoke(main, ["--profile-path", str(profiles_dir), "list"])
        assert result.exit_code == 0
        assert "minimal" in result.output
        assert "base-readonly" in result.output
        assert "python-dev" in result.output

    def test_list_empty(self, tmp_path):
        runner = CliRunner()
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        result = runner.invoke(main, ["--profile-path", str(empty_dir), "list"])
        assert result.exit_code == 0
        assert "No profiles found" in result.output


class TestValidate:
    def test_validate_valid(self, profiles_dir):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "validate", "minimal"],
        )
        assert result.exit_code == 0
        assert "Valid" in result.output

    def test_validate_cycle(self, profiles_dir):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "validate", "cycle-a"],
        )
        assert result.exit_code == 1
        assert "Circular" in result.output

    def test_validate_not_found(self, profiles_dir):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "validate", "nonexistent-xyz"],
        )
        assert result.exit_code == 1
        assert "not found" in result.output


class TestShow:
    def test_show_full(self, profiles_dir):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "show", "minimal"],
        )
        assert result.exit_code == 0
        assert "Read" in result.output

    def test_show_section(self, profiles_dir):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "show", "python-dev", "-s", "settings.permissions"],
        )
        assert result.exit_code == 0
        assert "allow" in result.output
        assert "Read" in result.output

    def test_show_missing_section(self, profiles_dir):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "show", "minimal", "-s", "nonexistent"],
        )
        assert result.exit_code == 1


class TestDiff:
    def test_diff_different(self, profiles_dir):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "diff", "minimal", "base-readonly"],
        )
        assert result.exit_code == 0
        assert "---" in result.output  # unified diff header

    def test_diff_identical(self, profiles_dir):
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["--profile-path", str(profiles_dir), "diff", "minimal", "minimal"],
        )
        assert result.exit_code == 0
        assert "identical" in result.output


class TestInit:
    def test_init_to_stdout(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / ".claude").mkdir()
        (source / ".claude" / "settings.json").write_text('{"model": "opus"}')

        runner = CliRunner()
        result = runner.invoke(
            main,
            ["init", "--name", "test", "--source-dir", str(source)],
        )
        assert result.exit_code == 0
        assert "[profile]" in result.output
        assert "opus" in result.output

    def test_init_to_file(self, tmp_path):
        source = tmp_path / "source"
        source.mkdir()
        (source / ".claude").mkdir()
        (source / ".claude" / "settings.json").write_text('{"model": "opus"}')

        out = tmp_path / "out.toml"
        runner = CliRunner()
        result = runner.invoke(
            main,
            ["init", "--name", "test", "--source-dir", str(source), "-o", str(out)],
        )
        assert result.exit_code == 0
        assert out.is_file()
        assert "opus" in out.read_text()
