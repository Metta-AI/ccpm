"""Reverse-engineer current Claude Code config into a TOML profile."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import tomli_w


def init_profile(
    source_dir: Path | None = None,
    output_path: Path | None = None,
    profile_name: str = "my-profile",
) -> str:
    """Read existing Claude Code config and produce a TOML profile.

    If source_dir is None, reads from ~/.claude/ and ~/.
    Returns the TOML string.
    """
    home = Path.home()
    source = source_dir or home

    profile: dict[str, Any] = {
        "profile": {
            "name": profile_name,
            "description": "Auto-generated from existing configuration",
        }
    }

    # Read settings.json
    settings_path = source / ".claude" / "settings.json"
    if settings_path.is_file():
        settings = json.loads(settings_path.read_text())
        # Transform hooks from Claude Code format to TOML format
        if "hooks" in settings:
            settings["hooks"] = _reverse_hooks(settings["hooks"])
        profile["settings"] = settings

    # Read CLAUDE.md
    claude_md_path = source / "CLAUDE.md"
    if claude_md_path.is_file():
        content = claude_md_path.read_text().strip()
        if content:
            profile["claude_md"] = {"strategy": "replace", "content": content}

    # Read .mcp.json
    mcp_path = source / ".mcp.json"
    if mcp_path.is_file():
        mcp_data = json.loads(mcp_path.read_text())
        servers = []
        for name, config in mcp_data.items():
            server = {"name": name, **config}
            servers.append(server)
        if servers:
            profile["mcp_servers"] = servers

    # Read env vars from .env.claude if it exists
    env_path = source / ".env.claude"
    if env_path.is_file():
        env = {}
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                kv = line[7:]  # strip 'export '
                key, _, value = kv.partition("=")
                env[key] = value.strip('"')
        if env:
            profile["env"] = env

    toml_str = tomli_w.dumps(profile)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(toml_str)

    return toml_str


def _reverse_hooks(hooks: dict[str, Any]) -> dict[str, Any]:
    """Convert Claude Code hooks JSON to TOML-friendly format.

    Input (Claude Code):
        {"PostToolUse": [{"matcher": "Edit|Write", "hooks": [{"type": "command", "command": "fmt.sh"}]}]}

    Output (TOML):
        {"PostToolUse": [{"matcher": "Edit|Write", "commands": ["fmt.sh"]}]}
    """
    result: dict[str, Any] = {}
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            result[event] = groups
            continue
        converted = []
        for group in groups:
            if not isinstance(group, dict):
                converted.append(group)
                continue
            entry: dict[str, Any] = {}
            if "matcher" in group:
                entry["matcher"] = group["matcher"]
            hook_list = group.get("hooks", [])
            entry["commands"] = [
                h["command"] for h in hook_list if isinstance(h, dict) and "command" in h
            ]
            if entry["commands"]:
                converted.append(entry)
        result[event] = converted
    return result
