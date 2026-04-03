"""Profile chain resolution with cycle detection and search path traversal."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


class ProfileNotFound(Exception):
    def __init__(self, name: str, search_path: list[Path], referenced_by: str = ""):
        self.name = name
        lines = [f'Profile "{name}" not found']
        if referenced_by:
            lines.append(f"  Referenced by: {referenced_by}")
        lines.append("  Search path:")
        for i, p in enumerate(search_path, 1):
            lines.append(f"    {i}. {p}")
        super().__init__("\n".join(lines))


class CycleError(Exception):
    def __init__(self, chain: list[str], name: str):
        cycle = " -> ".join(chain) + f" -> {name}"
        super().__init__(f"Circular profile dependency: {cycle}")


def locate_profile(name: str, search_path: list[Path]) -> Path:
    """Find a profile TOML file on the search path. Accepts name or path."""
    # If it's already a path to a file
    p = Path(name)
    if p.is_file():
        return p
    if p.with_suffix(".toml").is_file():
        return p.with_suffix(".toml")

    # Search directories
    for directory in search_path:
        candidate = directory / f"{name}.toml"
        if candidate.is_file():
            return candidate
        # Also check without .toml in case name already has it
        candidate = directory / name
        if candidate.is_file():
            return candidate

    raise ProfileNotFound(name, search_path)


def load_profile(path: Path) -> dict[str, Any]:
    """Parse a TOML profile file and return its contents."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def resolve_chain(
    name: str,
    search_path: list[Path],
    _visited: list[str] | None = None,
    _referenced_by: str = "",
) -> list[tuple[str, Path, dict[str, Any]]]:
    """Resolve the full extends chain for a profile.

    Returns an ordered list of (name, path, parsed_data) tuples from base to leaf.
    Detects circular dependencies.
    """
    if _visited is None:
        _visited = []

    if name in _visited:
        raise CycleError(_visited, name)

    path = locate_profile(name, search_path)
    data = load_profile(path)

    profile_meta = data.get("profile", {})
    profile_name = profile_meta.get("name", name)
    extends = profile_meta.get("extends", [])

    _visited = [*_visited, profile_name]

    chain: list[tuple[str, Path, dict[str, Any]]] = []
    for parent_name in extends:
        chain.extend(
            resolve_chain(
                parent_name,
                search_path,
                _visited=_visited,
                _referenced_by=f"{profile_name} ({path.name})",
            )
        )

    # Deduplicate: if a profile appears multiple times (diamond dependency),
    # keep only the last occurrence (highest priority)
    seen: set[str] = set()
    deduped: list[tuple[str, Path, dict[str, Any]]] = []
    for item in reversed(chain):
        if item[0] not in seen:
            seen.add(item[0])
            deduped.append(item)
    chain = list(reversed(deduped))

    chain.append((profile_name, path, data))
    return chain
