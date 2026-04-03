"""Deploy compiled profile to remote systems via rsync/scp."""

from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from ccpm.core.compiler import CompiledProfile
from ccpm.emit import emit_all


def deploy_ssh(
    compiled: CompiledProfile,
    remote: str,
    dry_run: bool = False,
) -> list[Path]:
    """Deploy a compiled profile to a remote system via rsync.

    remote should be in the format: user@host:/path/to/target
    If no path is given, defaults to user's home directory.
    """
    staging = Path(tempfile.mkdtemp(prefix="ccpm-ssh-"))
    written = emit_all(compiled, staging)

    if dry_run:
        return written

    # Ensure trailing slash on staging so rsync copies contents, not the dir itself
    staging_str = str(staging) + "/"

    # If remote doesn't have a path component, add ~/
    if ":" not in remote:
        remote = f"{remote}:~/"
    elif remote.endswith(":"):
        remote = f"{remote}~/"

    cmd = ["rsync", "-avz", "--mkpath", staging_str, remote]
    subprocess.run(cmd, check=True)

    return written
