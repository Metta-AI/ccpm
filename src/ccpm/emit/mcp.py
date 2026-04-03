"""Emit .mcp.json from compiled MCP servers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def emit_mcp(servers: dict[str, dict[str, Any]], output_dir: Path) -> Path | None:
    """Write .mcp.json to output_dir/.mcp.json.

    Transforms from name-keyed dict to Claude Code's .mcp.json format.
    Returns the path written, or None if no servers.
    """
    if not servers:
        return None

    mcp_config: dict[str, Any] = {}
    for server_name, server_data in servers.items():
        entry: dict[str, Any] = {}
        # Copy all fields except 'name' (it becomes the key)
        for k, v in server_data.items():
            if k == "name":
                continue
            entry[k] = v
        mcp_config[server_name] = entry

    dest = output_dir / ".mcp.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(mcp_config, indent=2) + "\n")
    return dest
