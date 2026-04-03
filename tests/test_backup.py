"""Tests for backup functionality."""

import json

from ccpm.util.backup import backup_existing


class TestBackup:
    def test_backup_settings(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.json"
        settings.write_text('{"model": "opus"}')

        backup_dir = backup_existing(tmp_path)
        assert backup_dir is not None
        assert (backup_dir / ".claude" / "settings.json").is_file()
        assert json.loads((backup_dir / ".claude" / "settings.json").read_text())["model"] == "opus"

    def test_backup_claude_md(self, tmp_path):
        (tmp_path / "CLAUDE.md").write_text("# Rules")

        backup_dir = backup_existing(tmp_path)
        assert backup_dir is not None
        assert (backup_dir / "CLAUDE.md").is_file()
        assert "Rules" in (backup_dir / "CLAUDE.md").read_text()

    def test_backup_nothing_returns_none(self, tmp_path):
        assert backup_existing(tmp_path) is None

    def test_backup_preserves_originals(self, tmp_path):
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        settings = claude_dir / "settings.json"
        settings.write_text('{"model": "opus"}')

        backup_existing(tmp_path)
        # Original should still exist
        assert settings.is_file()
        assert json.loads(settings.read_text())["model"] == "opus"

    def test_backup_directory_assets(self, tmp_path):
        skills_dir = tmp_path / ".claude" / "skills" / "my-skill"
        skills_dir.mkdir(parents=True)
        (skills_dir / "SKILL.md").write_text("# Skill")

        backup_dir = backup_existing(tmp_path)
        assert (backup_dir / ".claude" / "skills" / "my-skill" / "SKILL.md").is_file()
