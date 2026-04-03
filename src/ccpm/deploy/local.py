"""Deploy compiled profile to local filesystem."""

from __future__ import annotations

import shutil
from pathlib import Path

from ccpm.core.compiler import CompiledProfile
from ccpm.emit import emit_all
from ccpm.util.backup import backup_existing


def deploy_local(
    compiled: CompiledProfile,
    target_dir: Path,
    backup: bool = True,
    dry_run: bool = False,
) -> list[Path]:
    """Deploy a compiled profile to a local directory.

    If target_dir is ~ (home), writes to ~/.claude/ and ~/CLAUDE.md.
    If target_dir is a project, writes to <project>/.claude/ and <project>/CLAUDE.md.
    """
    target_dir = target_dir.expanduser().resolve()

    if dry_run:
        import tempfile

        staging = Path(tempfile.mkdtemp(prefix="ccpm-dry-run-"))
        return emit_all(compiled, staging)

    if backup:
        backup_dir = backup_existing(target_dir)
        if backup_dir:
            from rich.console import Console

            Console(stderr=True).print(f"[dim]Backed up existing config to {backup_dir}[/dim]")

    return emit_all(compiled, target_dir)
