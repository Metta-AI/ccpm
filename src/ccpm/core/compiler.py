"""Orchestrator: resolve -> expand -> step-by-step merge -> CompiledProfile."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from ccpm.core.deep_merge import deep_merge
from ccpm.core.env import expand_env
from ccpm.core.resolver import resolve_chain


class CompiledProfile:
    """The fully merged result of compiling a profile chain."""

    def __init__(self, data: dict[str, Any], chain_names: list[str]):
        self.data = data
        self.chain_names = chain_names

    @property
    def settings(self) -> dict[str, Any]:
        return self.data.get("settings", {})

    @property
    def claude_md_entries(self) -> list[dict[str, Any]]:
        """List of claude_md entries in chain order (for append/prepend/replace)."""
        return self.data.get("_claude_md_chain", [])

    @property
    def mcp_servers(self) -> dict[str, dict[str, Any]]:
        return self.data.get("_mcp_servers", {})

    @property
    def skills(self) -> list[dict[str, Any]]:
        return self.data.get("skills", [])

    @property
    def commands(self) -> list[dict[str, Any]]:
        return self.data.get("commands", [])

    @property
    def agents(self) -> list[dict[str, Any]]:
        return self.data.get("agents", [])

    @property
    def hook_scripts(self) -> list[dict[str, Any]]:
        return self.data.get("hook_scripts", [])

    @property
    def env(self) -> dict[str, str]:
        return self.data.get("env", {})

    @property
    def credentials(self) -> list[dict[str, Any]]:
        return self.data.get("credentials", [])

    @property
    def shell(self) -> list[dict[str, Any]]:
        """Shell config entries in chain order (for append/replace)."""
        return self.data.get("_shell_chain", [])


def compile_profile(
    name: str,
    search_path: list[Path],
    env_overrides: dict[str, str] | None = None,
    verbose: bool = False,
) -> CompiledProfile:
    """Compile a profile by resolving its chain and deep-merging step by step."""
    chain = resolve_chain(name, search_path)
    chain_names = [entry[0] for entry in chain]

    if verbose:
        from rich.console import Console

        console = Console(stderr=True)
        console.print(f"[dim]Resolved chain: {' -> '.join(chain_names)}[/dim]")

    acc: dict[str, Any] = {}
    claude_md_chain: list[dict[str, Any]] = []
    shell_chain: list[dict[str, Any]] = []

    for i, (profile_name, path, raw_data) in enumerate(chain):
        # Load env_file references before env expansion so their vars are available
        _load_env_files(raw_data, profile_path=path, env_overrides=env_overrides)

        # Expand env vars in this profile's data
        expanded = expand_env(raw_data, overrides=env_overrides, context=profile_name)

        # Extract special sections that need non-dict merge handling
        profile_data = copy.deepcopy(expanded)

        # Remove profile metadata (not part of the merged output)
        profile_data.pop("profile", None)

        # Collect claude_md entries separately (they chain, not merge)
        claude_md = profile_data.pop("claude_md", None)
        if claude_md:
            claude_md_chain.append(claude_md)

        # Collect shell entries separately (they chain, not merge)
        shell = profile_data.pop("shell", None)
        if shell:
            shell_chain.append(shell)

        # Collect mcp_servers and merge by name
        mcp_servers = profile_data.pop("mcp_servers", [])
        if mcp_servers:
            if "_mcp_servers" not in acc:
                acc["_mcp_servers"] = {}
            for server in mcp_servers:
                server_name = server.get("name", f"unnamed_{len(acc['_mcp_servers'])}")
                if server_name in acc["_mcp_servers"]:
                    deep_merge(acc["_mcp_servers"][server_name], server)
                else:
                    acc["_mcp_servers"][server_name] = copy.deepcopy(server)

        # Resolve credentials: pull values from env/commands into env dict
        credentials = profile_data.get("credentials", [])
        if credentials:
            resolved_env = _resolve_credentials(credentials, env_overrides or {})
            if "env" not in profile_data:
                profile_data["env"] = {}
            profile_data["env"].update(resolved_env)

        # Resolve file references in any dict section (settings, env, etc.)
        _resolve_file_refs(profile_data, profile_path=path)

        # Transform hooks from TOML format to intermediate format before merging
        if "settings" in profile_data and "hooks" in profile_data["settings"]:
            profile_data["settings"]["hooks"] = _transform_hooks_for_merge(
                profile_data["settings"]["hooks"]
            )

        # Deep merge everything else
        deep_merge(acc, profile_data)

        if verbose:
            from rich.console import Console

            console = Console(stderr=True)
            console.print(f"[dim]  Step {i + 1}: merged {profile_name}[/dim]")

    # Attach chained sections
    acc["_claude_md_chain"] = claude_md_chain
    acc["_shell_chain"] = shell_chain

    return CompiledProfile(acc, chain_names)


class MissingCredential(Exception):
    def __init__(self, name: str, env_var: str, description: str = ""):
        lines = [f"Missing credential: {name} (${env_var})"]
        if description:
            lines.append(f"  Description: {description}")
        lines.append(f"  Hint: Set {env_var} in your environment, pass --var {env_var}=..., or add a source command")
        super().__init__("\n".join(lines))


def _load_env_files(data: dict[str, Any], profile_path: Path, env_overrides: dict[str, str] | None = None) -> None:
    """Load variables from env_file references into the env section.

    Supports:
        [env]
        env_file = ".env"           # single file
        env_files = [".env", ".env.local"]  # multiple files
    """
    env_section = data.get("env", {})
    if not isinstance(env_section, dict):
        return

    files: list[str] = []
    if "env_file" in env_section:
        files.append(env_section.pop("env_file"))
    if "env_files" in env_section:
        files.extend(env_section.pop("env_files"))

    # Load files in order — later files override earlier ones
    file_loaded: dict[str, str] = {}
    for file_ref in files:
        file_path = Path(file_ref)
        if not file_path.is_absolute():
            file_path = profile_path.parent / file_path

        if not file_path.is_file():
            raise FileNotFoundError(
                f"env_file not found: {file_path}\n"
                f"  Referenced by: env.env_file in {profile_path.name}"
            )

        file_loaded.update(_parse_env_file(file_path))

    # Merge: file-loaded vars are the base, inline TOML vars override,
    # CLI overrides beat everything
    for key, value in file_loaded.items():
        if key not in env_section:  # inline TOML wins over file
            env_section[key] = value

    if env_section:
        data["env"] = env_section


def _parse_env_file(path: Path) -> dict[str, str]:
    """Parse a .env file (KEY=VALUE lines, # comments, optional quotes)."""
    result: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Strip 'export ' prefix
        if line.startswith("export "):
            line = line[7:]
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
            value = value[1:-1]
        result[key] = value
    return result


def _resolve_credentials(
    credentials: list[dict[str, Any]],
    env_overrides: dict[str, str],
) -> dict[str, str]:
    """Resolve credential declarations into env var key-value pairs.

    Each credential entry:
        [[credentials]]
        name = "anthropic-api-key"
        env_var = "ANTHROPIC_API_KEY"
        description = "Anthropic API key for Claude"
        # Optional: command to fetch the value
        source = "op read 'op://Dev/Anthropic/api-key'"
        # Optional: skip if not available (default: false = required)
        optional = false

    Resolution order:
    1. CLI --var overrides
    2. OS environment
    3. source command (if provided)
    4. Error if required and not found
    """
    import os
    import subprocess

    resolved: dict[str, str] = {}

    for cred in credentials:
        env_var = cred["env_var"]
        name = cred.get("name", env_var)
        description = cred.get("description", "")
        source_cmd = cred.get("source")
        optional = cred.get("optional", False)

        # 1. CLI override
        if env_var in env_overrides:
            resolved[env_var] = env_overrides[env_var]
            continue

        # 2. OS environment
        if env_var in os.environ:
            resolved[env_var] = os.environ[env_var]
            continue

        # 3. Source command
        if source_cmd:
            try:
                result = subprocess.run(
                    source_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0 and result.stdout.strip():
                    resolved[env_var] = result.stdout.strip()
                    continue
            except (subprocess.TimeoutExpired, OSError):
                pass

        # 4. Missing
        if not optional:
            raise MissingCredential(name, env_var, description)

    return resolved


def _resolve_file_refs(data: dict[str, Any], profile_path: Path) -> None:
    """Resolve `file` references in dict sections.

    If a section like `settings` has a `file` key pointing to a JSON file,
    load the JSON, then deep-merge any inline keys on top.
    This lets you write:

        [settings]
        file = "base/settings.json"
        model = "opus"    # overrides on top of the loaded file

    The file path is resolved relative to the profile's directory.
    """
    for key, value in list(data.items()):
        if not isinstance(value, dict):
            continue
        if "file" not in value:
            continue

        file_path = Path(value["file"])
        if not file_path.is_absolute():
            file_path = profile_path.parent / file_path

        if not file_path.is_file():
            raise FileNotFoundError(
                f"File reference not found: {file_path}\n"
                f"  Referenced by: {key}.file in {profile_path.name}"
            )

        suffix = file_path.suffix.lower()
        if suffix == ".json":
            loaded = json.loads(file_path.read_text())
        elif suffix == ".toml":
            import tomllib

            loaded = tomllib.loads(file_path.read_text())
        else:
            raise ValueError(
                f"Unsupported file type '{suffix}' for {key}.file in {profile_path.name}\n"
                f"  Supported: .json, .toml"
            )

        # Remove the file key, keep any inline overrides
        inline = {k: v for k, v in value.items() if k != "file"}

        # Start with loaded file content, merge inline overrides on top
        merged = copy.deepcopy(loaded)
        if inline:
            deep_merge(merged, inline)

        data[key] = merged


def _transform_hooks_for_merge(hooks: dict[str, Any]) -> dict[str, Any]:
    """Transform TOML hooks format for merging.

    TOML input has each event as a list of hook groups with 'commands' arrays.
    We transform to the intermediate merge format where each event is a list
    of hook group dicts.
    """
    result: dict[str, Any] = {}
    for event_name, groups in hooks.items():
        if isinstance(groups, list):
            result[event_name] = groups
        else:
            result[event_name] = [groups]
    return result
