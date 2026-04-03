"""Click CLI for ccpm."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from ccpm.core.compiler import compile_profile
from ccpm.emit import emit_all
from ccpm.util.discovery import get_search_path, list_profiles

console = Console()
err_console = Console(stderr=True)


def _parse_vars(ctx, param, value) -> dict[str, str]:
    """Parse --var KEY=VALUE pairs into a dict."""
    result = {}
    for item in value:
        if "=" not in item:
            raise click.BadParameter(f"Expected KEY=VALUE, got: {item}")
        k, _, v = item.partition("=")
        result[k] = v
    return result


@click.group()
@click.option(
    "--profile-path",
    multiple=True,
    type=click.Path(exists=True, file_okay=False, path_type=Path),
    help="Additional profile search directories.",
)
@click.pass_context
def main(ctx, profile_path):
    """ccpm - Claude Code Profile Manager.

    Compose, build, and deploy layered Claude Code configurations.
    """
    ctx.ensure_object(dict)
    ctx.obj["extra_dirs"] = list(profile_path)


@main.command()
@click.argument("profile")
@click.option(
    "--output-dir", "-o",
    type=click.Path(path_type=Path),
    default=None,
    help="Output directory. Defaults to a temp staging dir.",
)
@click.option("--var", multiple=True, callback=_parse_vars, expose_value=True, help="Set env var: KEY=VALUE.")
@click.option("--session", "session_log", type=click.Path(exists=True), default=None, help="Session log (.jsonl) to include for resumption.")
@click.option("--verbose", "-v", is_flag=True, help="Show merge decisions.")
@click.pass_context
def build(ctx, profile, output_dir, var, session_log, verbose):
    """Compile a profile into resolved config files."""
    search_path = get_search_path(ctx.obj["extra_dirs"])
    compiled = compile_profile(profile, search_path, env_overrides=var, verbose=verbose, session_log=session_log)

    if output_dir is None:
        output_dir = Path(tempfile.mkdtemp(prefix="ccpm-build-"))

    written = emit_all(compiled, output_dir)

    console.print(f"[bold]Resolved chain:[/bold] {' -> '.join(compiled.chain_names)}")
    for path in written:
        rel = path.relative_to(output_dir)
        console.print(f"  [green]+[/green] {rel}")
    console.print(f"\n[bold]{len(written)} files[/bold] written to {output_dir}")


@main.command()
@click.argument("profile")
@click.argument("target")
@click.option("--project", type=click.Path(path_type=Path), default=None, help="Project directory for local deploy.")
@click.option("--var", multiple=True, callback=_parse_vars, expose_value=True, help="Set env var: KEY=VALUE.")
@click.option("--session", "session_log", type=click.Path(exists=True), default=None, help="Session log (.jsonl) to include for resumption.")
@click.option("--dry-run", is_flag=True, help="Show what would change without writing.")
@click.option("--no-backup", is_flag=True, help="Skip backup of existing config.")
@click.option("--verbose", "-v", is_flag=True, help="Show merge decisions.")
@click.option("--docker-target-path", default="/root", help="Target path inside Docker container.")
@click.pass_context
def deploy(ctx, profile, target, project, var, session_log, dry_run, no_backup, verbose, docker_target_path):
    """Build and deploy a profile to a target.

    TARGET can be: local, docker CONTAINER, ssh USER@HOST, or dir PATH
    """
    search_path = get_search_path(ctx.obj["extra_dirs"])
    compiled = compile_profile(profile, search_path, env_overrides=var, verbose=verbose, session_log=session_log)

    console.print(f"[bold]Resolved chain:[/bold] {' -> '.join(compiled.chain_names)}")

    if target == "local":
        from ccpm.deploy.local import deploy_local

        target_dir = project or Path.home()
        written = deploy_local(compiled, target_dir, backup=not no_backup, dry_run=dry_run)
        label = f"local ({target_dir})"
    elif target.startswith("docker"):
        parts = target.split(maxsplit=1)
        if len(parts) < 2:
            raise click.BadParameter("docker target requires container name: 'docker CONTAINER'")
        from ccpm.deploy.docker import deploy_docker

        container = parts[1]
        written = deploy_docker(compiled, container, target_path=docker_target_path, dry_run=dry_run)
        label = f"docker ({container})"
    elif target.startswith("ssh"):
        parts = target.split(maxsplit=1)
        if len(parts) < 2:
            raise click.BadParameter("ssh target requires remote: 'ssh USER@HOST'")
        from ccpm.deploy.ssh import deploy_ssh

        written = deploy_ssh(compiled, parts[1], dry_run=dry_run)
        label = f"ssh ({parts[1]})"
    else:
        # Treat as directory path
        target_path = Path(target)
        written = emit_all(compiled, target_path)
        label = f"dir ({target_path})"

    prefix = "[yellow](dry run)[/yellow] " if dry_run else ""
    for path in written:
        console.print(f"  {prefix}[green]+[/green] {path}")
    console.print(f"\n{prefix}[bold]{len(written)} files[/bold] deployed to {label}")


@main.command("list")
@click.pass_context
def list_cmd(ctx):
    """List available profiles."""
    search_path = get_search_path(ctx.obj["extra_dirs"])
    profiles = list_profiles(search_path)

    if not profiles:
        console.print("[dim]No profiles found. Create one in ~/.claude/profiles/[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Path", style="dim")

    for name, path, desc in profiles:
        table.add_row(name, desc, str(path))

    console.print(table)


@main.command()
@click.argument("profile")
@click.option("--var", multiple=True, callback=_parse_vars, expose_value=True, help="Set env var: KEY=VALUE.")
@click.pass_context
def validate(ctx, profile, var):
    """Validate a profile (syntax, references, cycles)."""
    search_path = get_search_path(ctx.obj["extra_dirs"])
    try:
        compiled = compile_profile(profile, search_path, env_overrides=var)
        console.print(f"[green]Valid.[/green] Chain: {' -> '.join(compiled.chain_names)}")
    except Exception as e:
        console.print(f"[red]Invalid:[/red] {e}")
        raise SystemExit(1)


@main.command()
@click.argument("profile")
@click.option("--section", "-s", default=None, help="Show only this section (e.g. settings.permissions).")
@click.option("--var", multiple=True, callback=_parse_vars, expose_value=True, help="Set env var: KEY=VALUE.")
@click.option("--verbose", "-v", is_flag=True, help="Show merge decisions.")
@click.pass_context
def show(ctx, profile, section, var, verbose):
    """Show the fully resolved config for a profile."""
    search_path = get_search_path(ctx.obj["extra_dirs"])
    compiled = compile_profile(profile, search_path, env_overrides=var, verbose=verbose)

    console.print(f"[bold]Chain:[/bold] {' -> '.join(compiled.chain_names)}\n")

    data = compiled.data
    if section:
        parts = section.split(".")
        for part in parts:
            if isinstance(data, dict) and part in data:
                data = data[part]
            else:
                console.print(f"[red]Section not found:[/red] {section}")
                raise SystemExit(1)

    console.print_json(json.dumps(data, indent=2, default=str))


@main.command()
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None, help="Output file path.")
@click.option("--name", default="my-profile", help="Profile name.")
@click.option("--source-dir", type=click.Path(exists=True, path_type=Path), default=None, help="Source directory to read from.")
def init(output, name, source_dir):
    """Reverse-engineer current config into a TOML profile."""
    from ccpm.util.init import init_profile

    toml_str = init_profile(source_dir=source_dir, output_path=output, profile_name=name)

    if output:
        console.print(f"[green]Profile written to {output}[/green]")
    else:
        click.echo(toml_str)


@main.command()
@click.argument("profile_a")
@click.argument("profile_b")
@click.option("--var", multiple=True, callback=_parse_vars, expose_value=True, help="Set env var: KEY=VALUE.")
@click.pass_context
def diff(ctx, profile_a, profile_b, var):
    """Compare two resolved profiles."""
    import difflib

    search_path = get_search_path(ctx.obj["extra_dirs"])
    compiled_a = compile_profile(profile_a, search_path, env_overrides=var)
    compiled_b = compile_profile(profile_b, search_path, env_overrides=var)

    json_a = json.dumps(compiled_a.data, indent=2, sort_keys=True, default=str)
    json_b = json.dumps(compiled_b.data, indent=2, sort_keys=True, default=str)

    diff_lines = difflib.unified_diff(
        json_a.splitlines(),
        json_b.splitlines(),
        fromfile=profile_a,
        tofile=profile_b,
        lineterm="",
    )

    output = "\n".join(diff_lines)
    if output:
        console.print(output)
    else:
        console.print("[green]Profiles are identical.[/green]")
