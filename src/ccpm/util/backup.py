"""Backup existing config before overwrite."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

BACKUP_DIR_NAME = ".ccpm-backups"


def backup_existing(target_dir: Path) -> Path | None:
    """Back up existing Claude Code config files before deploying.

    Returns the backup directory path, or None if nothing to back up.
    """
    files_to_backup = [
        target_dir / ".claude" / "settings.json",
        target_dir / ".claude" / "settings.local.json",
        target_dir / "CLAUDE.md",
        target_dir / ".mcp.json",
        target_dir / ".env.claude",
    ]
    dirs_to_backup = [
        target_dir / ".claude" / "skills",
        target_dir / ".claude" / "commands",
        target_dir / ".claude" / "agents",
        target_dir / ".claude" / "hooks",
    ]

    exists = [f for f in files_to_backup if f.exists()] + [
        d for d in dirs_to_backup if d.exists()
    ]
    if not exists:
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = target_dir / BACKUP_DIR_NAME / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    for item in exists:
        rel = item.relative_to(target_dir)
        dest = backup_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    return backup_dir
