"""Tests for profile chain resolution and cycle detection."""

import pytest

from ccpm.core.resolver import (
    CycleError,
    ProfileNotFound,
    locate_profile,
    resolve_chain,
)


class TestLocateProfile:
    def test_find_by_name(self, search_path):
        path = locate_profile("minimal", search_path)
        assert path.name == "minimal.toml"
        assert path.is_file()

    def test_find_by_name_with_extension(self, search_path):
        path = locate_profile("minimal.toml", search_path)
        assert path.name == "minimal.toml"

    def test_find_by_absolute_path(self, profiles_dir):
        path = locate_profile(str(profiles_dir / "minimal.toml"), [])
        assert path.name == "minimal.toml"

    def test_not_found(self, search_path):
        with pytest.raises(ProfileNotFound) as exc_info:
            locate_profile("nonexistent-profile-xyz", search_path)
        assert "nonexistent-profile-xyz" in str(exc_info.value)
        assert "Search path:" in str(exc_info.value)


class TestResolveChain:
    def test_no_extends(self, search_path):
        chain = resolve_chain("minimal", search_path)
        assert len(chain) == 1
        assert chain[0][0] == "minimal"

    def test_single_extends(self, search_path):
        chain = resolve_chain("git-permissions", search_path)
        assert len(chain) == 1
        names = [c[0] for c in chain]
        assert names == ["git-permissions"]

    def test_multi_level_extends(self, search_path):
        chain = resolve_chain("python-dev", search_path)
        names = [c[0] for c in chain]
        assert names == [
            "base-readonly",
            "git-permissions",
            "edit-permissions",
            "python-dev",
        ]

    def test_deep_extends(self, search_path):
        """full-featured extends python-dev which extends 3 others."""
        chain = resolve_chain("full-featured", search_path)
        names = [c[0] for c in chain]
        assert names == [
            "base-readonly",
            "git-permissions",
            "edit-permissions",
            "python-dev",
            "full-featured",
        ]

    def test_chain_returns_parsed_data(self, search_path):
        chain = resolve_chain("minimal", search_path)
        _, _, data = chain[0]
        assert "profile" in data
        assert data["profile"]["name"] == "minimal"
        assert "settings" in data

    def test_cycle_detection(self, search_path):
        with pytest.raises(CycleError) as exc_info:
            resolve_chain("cycle-a", search_path)
        msg = str(exc_info.value)
        assert "cycle-a" in msg
        assert "cycle-b" in msg
        assert "Circular" in msg

    def test_diamond_deduplication(self, search_path):
        """diamond-top -> diamond-b -> diamond-a AND diamond-c -> diamond-a.
        diamond-a should appear only once (deduped to last occurrence)."""
        chain = resolve_chain("diamond-top", search_path)
        names = [c[0] for c in chain]
        assert names.count("diamond-a") == 1
        # Dedup keeps last occurrence: b's diamond-a is removed, c's is kept
        assert names == ["diamond-b", "diamond-a", "diamond-c", "diamond-top"]
