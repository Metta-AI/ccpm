"""Emit settings.json from compiled profile."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any


def emit_settings(settings: dict[str, Any], output_dir: Path) -> Path | None:
    """Write settings.json to output_dir/.claude/settings.json.

    Transforms hooks from intermediate format to Claude Code's expected structure.
    Returns the path written, or None if no settings.
    """
    if not settings:
        return None

    out = copy.deepcopy(settings)

    # Transform hooks to Claude Code format
    if "hooks" in out:
        out["hooks"] = _to_claude_hooks(out["hooks"])

    dest = output_dir / ".claude" / "settings.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2) + "\n")
    return dest


def _to_claude_hooks(hooks: dict[str, Any]) -> dict[str, Any]:
    """Convert hooks from intermediate/TOML format to Claude Code JSON format.

    Input (from TOML):
        {"PostToolUse": [{"matcher": "Edit|Write", "commands": ["format.sh"]}]}

    Output (Claude Code settings.json):
        {"PostToolUse": [{"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "format.sh"}]}]}
    """
    result: dict[str, Any] = {}
    for event_name, groups in hooks.items():
        if not isinstance(groups, list):
            groups = [groups]
        converted_groups = []
        for group in groups:
            if isinstance(group, dict):
                converted = {}
                if "matcher" in group:
                    converted["matcher"] = group["matcher"]
                commands = group.get("commands", [])
                converted["hooks"] = [
                    {"type": "command", "command": cmd} for cmd in commands
                ]
                converted_groups.append(converted)
            else:
                converted_groups.append(group)
        result[event_name] = converted_groups
    return result
