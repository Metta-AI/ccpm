"""Tests for profile discovery and search path."""

from pathlib import Path

from ccpm.util.discovery import get_search_path, list_profiles


class TestSearchPath:
    def test_extra_dirs_included(self, tmp_path):
        extra = tmp_path / "extra"
        extra.mkdir()
        path = get_search_path(extra_dirs=[extra])
        assert extra in path

    def test_env_var_path(self, tmp_path, monkeypatch):
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        monkeypatch.setenv("CLAUDE_PROFILE_PATH", f"{d1}:{d2}")
        path = get_search_path()
        assert d1 in path
        assert d2 in path

    def test_empty_env_var(self, monkeypatch):
        monkeypatch.setenv("CLAUDE_PROFILE_PATH", "")
        path = get_search_path()
        # Should not crash, should still include global/project dirs if they exist
        assert isinstance(path, list)


class TestListProfiles:
    def test_list_from_examples(self, profiles_dir):
        profiles = list_profiles([profiles_dir])
        names = [p[0] for p in profiles]
        assert "minimal" in names
        assert "base-readonly" in names
        assert "python-dev" in names
        assert "full-featured" in names

    def test_list_includes_description(self, profiles_dir):
        profiles = list_profiles([profiles_dir])
        by_name = {p[0]: p[2] for p in profiles}
        assert by_name["minimal"] == "Bare minimum read-only access"

    def test_list_empty_dir(self, tmp_path):
        profiles = list_profiles([tmp_path])
        assert profiles == []

    def test_list_deduplicates(self, profiles_dir):
        # Same dir twice should not produce duplicates
        profiles = list_profiles([profiles_dir, profiles_dir])
        names = [p[0] for p in profiles]
        assert len(names) == len(set(names))
