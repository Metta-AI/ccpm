"""Emit .env.claude from compiled environment variables."""

from __future__ import annotations

from pathlib import Path


def emit_env_file(env: dict[str, str], output_dir: Path) -> Path | None:
    """Write .env.claude with export KEY=VALUE lines.

    Returns the path written, or None if no env vars.
    """
    if not env:
        return None

    lines = [f'export {key}="{value}"' for key, value in sorted(env.items())]

    dest = output_dir / ".env.claude"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n")
    return dest
