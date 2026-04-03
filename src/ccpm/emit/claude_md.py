"""Emit CLAUDE.md from the compiled claude_md chain."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def emit_claude_md(entries: list[dict[str, Any]], output_dir: Path) -> Path | None:
    """Write CLAUDE.md to output_dir/CLAUDE.md.

    Processes the chain of claude_md entries with their strategies
    (append/prepend/replace). Returns the path written, or None.
    """
    if not entries:
        return None

    result = ""
    for entry in entries:
        content = _resolve_content(entry)
        if not content:
            continue

        strategy = entry.get("strategy", "append")
        if strategy == "replace":
            result = content
        elif strategy == "prepend":
            result = content + ("\n\n" if result else "") + result
        else:  # append
            result = result + ("\n\n" if result else "") + content

    if not result:
        return None

    dest = output_dir / "CLAUDE.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(result.rstrip() + "\n")
    return dest


def _resolve_content(entry: dict[str, Any]) -> str:
    """Get content from inline string or file reference."""
    if "content" in entry and entry["content"]:
        return entry["content"].strip()
    if "file" in entry and entry["file"]:
        path = Path(entry["file"])
        if not path.is_file():
            raise FileNotFoundError(
                f"CLAUDE.md file reference not found: {path}\n"
                f"  Hint: Check that the path exists and env vars resolved correctly"
            )
        return path.read_text().strip()
    return ""
