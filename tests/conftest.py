"""Shared fixtures for ccpm tests."""

from __future__ import annotations

from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
PROFILES_DIR = EXAMPLES_DIR / "profiles"


@pytest.fixture
def examples_dir():
    return EXAMPLES_DIR


@pytest.fixture
def profiles_dir():
    return PROFILES_DIR


@pytest.fixture
def search_path(profiles_dir):
    return [profiles_dir]


@pytest.fixture
def tmp_output(tmp_path):
    """Temporary output directory for build/emit tests."""
    return tmp_path / "output"
