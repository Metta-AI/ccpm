"""Copy file assets (skills, commands, agents, hook scripts) to output."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


def emit_file_assets(
    assets: list[dict[str, Any]],
    asset_type: str,
    output_dir: Path,
) -> list[Path]:
    """Copy file assets to the appropriate subdirectory.

    asset_type is one of: skills, commands, agents, hook_scripts.
    Returns list of paths written.
    """
    type_to_subdir = {
        "skills": ".claude/skills",
        "commands": ".claude/commands",
        "agents": ".claude/agents",
        "hook_scripts": ".claude/hooks",
    }
    subdir = type_to_subdir.get(asset_type, f".claude/{asset_type}")
    written: list[Path] = []

    for asset in assets:
        # Inline content
        if asset.get("content") and asset.get("name"):
            dest = output_dir / subdir / asset["name"]
            if not dest.suffix:
                dest = dest.with_suffix(".md")
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(asset["content"])
            written.append(dest)
            continue

        source = asset.get("source")
        if not source:
            continue

        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(
                f"{asset_type} source not found: {source_path}\n"
                f"  Hint: Check that the path exists and env vars resolved correctly"
            )

        # Determine target path
        if asset.get("target"):
            dest = output_dir / asset["target"]
        elif asset_type == "hook_scripts":
            dest = output_dir / subdir / source_path.name
        elif source_path.is_dir():
            dest = output_dir / subdir / source_path.name
        else:
            dest = output_dir / subdir / source_path.name

        dest.parent.mkdir(parents=True, exist_ok=True)

        if source_path.is_dir():
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(source_path, dest)
        else:
            shutil.copy2(source_path, dest)

        written.append(dest)

    return written
