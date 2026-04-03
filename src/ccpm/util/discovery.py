"""Profile search path discovery."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_GLOBAL_DIR = Path.home() / ".claude" / "profiles"
DEFAULT_PROJECT_DIR = Path(".claude") / "profiles"


def get_search_path(extra_dirs: list[Path] | None = None) -> list[Path]:
    """Build the profile search path.

    Order: $CLAUDE_PROFILE_PATH -> ~/.claude/profiles/ -> ./.claude/profiles/
    Extra dirs from CLI are prepended.
    """
    dirs: list[Path] = []

    # CLI-provided extra dirs (highest search priority)
    if extra_dirs:
        dirs.extend(extra_dirs)

    # $CLAUDE_PROFILE_PATH
    env_path = os.environ.get("CLAUDE_PROFILE_PATH", "")
    if env_path:
        for p in env_path.split(":"):
            p = p.strip()
            if p:
                dirs.append(Path(p).expanduser().resolve())

    # Global
    if DEFAULT_GLOBAL_DIR.is_dir():
        dirs.append(DEFAULT_GLOBAL_DIR)

    # Project-local (cwd)
    project_dir = Path.cwd() / DEFAULT_PROJECT_DIR
    if project_dir.is_dir():
        dirs.append(project_dir)

    return dirs


def list_profiles(search_path: list[Path]) -> list[tuple[str, Path, str]]:
    """List all available profiles on the search path.

    Returns (name, path, description) tuples.
    """
    import tomllib

    profiles: list[tuple[str, Path, str]] = []
    seen: set[str] = set()

    for directory in search_path:
        if not directory.is_dir():
            continue
        for toml_file in sorted(directory.glob("*.toml")):
            name = toml_file.stem
            if name in seen:
                continue
            seen.add(name)
            try:
                with open(toml_file, "rb") as f:
                    data = tomllib.load(f)
                desc = data.get("profile", {}).get("description", "")
            except Exception:
                desc = "(error reading profile)"
            profiles.append((name, toml_file, desc))

    return profiles
