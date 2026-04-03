"""Emit compiled profiles to output directories."""

from __future__ import annotations

from pathlib import Path

from ccpm.core.compiler import CompiledProfile
from ccpm.emit.claude_md import emit_claude_md
from ccpm.emit.env_file import emit_env_file
from ccpm.emit.files import emit_file_assets
from ccpm.emit.mcp import emit_mcp
from ccpm.emit.settings import emit_settings
from ccpm.emit.shell import emit_shell


def emit_all(compiled: CompiledProfile, output_dir: Path) -> list[Path]:
    """Emit all config files from a compiled profile. Returns paths written."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    path = emit_settings(compiled.settings, output_dir)
    if path:
        written.append(path)

    path = emit_claude_md(compiled.claude_md_entries, output_dir)
    if path:
        written.append(path)

    path = emit_mcp(compiled.mcp_servers, output_dir)
    if path:
        written.append(path)

    path = emit_env_file(compiled.env, output_dir)
    if path:
        written.append(path)

    path = emit_shell(compiled.shell, output_dir)
    if path:
        written.append(path)

    for asset_type in ("skills", "commands", "agents", "hook_scripts"):
        assets = getattr(compiled, asset_type)
        written.extend(emit_file_assets(assets, asset_type, output_dir))

    return written
