# ccpm - Claude Code Profile Manager

Composable, layered configuration profiles for Claude Code. Define reusable building blocks in TOML, compose them with `extends`, and deploy complete configurations to local machines, Docker containers, or remote systems.

## Why

Claude Code's config is spread across `settings.json`, `CLAUDE.md`, `.mcp.json`, skills, hooks, commands, agents, and env vars. There's no way to compose, version, or deploy a full configuration as a unit. ccpm fixes that:

- **Compose**: Build profiles from reusable layers (read-only base, git permissions, python tooling)
- **Merge**: Deep recursive merge at every level - dicts recurse, lists accumulate, scalars replace
- **Deploy**: Push complete configs to local, Docker, or SSH targets with backup

## Install

```bash
# With uv
uv tool install ccpm

# With pipx
pipx install ccpm

# From source
git clone https://github.com/Metta-AI/ccpm.git
cd ccpm
uv sync
```

Both `ccpm` and `claude-profile` are registered as CLI entry points.

## Quick Start

### 1. Create a base profile

```toml
# ~/.claude/profiles/base-readonly.toml
[profile]
name = "base-readonly"
description = "Safe read-only defaults"

[settings]
effortLevel = "medium"

[settings.permissions]
allow = ["Read", "Glob", "Grep", "WebFetch"]

[env]
CLAUDE_CODE_USE_BEDROCK = "1"
```

### 2. Create a development profile that extends it

```toml
# ~/.claude/profiles/python-dev.toml
[profile]
name = "python-dev"
description = "Python development with testing"
extends = ["base-readonly", "git-permissions"]

[settings]
model = "us.anthropic.claude-opus-4-6-v1[1m]"
effortLevel = "high"

[settings.permissions]
allow = [
    "Edit",
    "Write",
    "Bash(pytest:*)",
    "Bash(ruff check:*)",
]
```

The merge result accumulates permissions from both profiles. `effortLevel` gets replaced by the child's value, while the parent's `allow` list gets extended (not replaced).

### 3. Build and deploy

```bash
# Build to a staging directory
ccpm build python-dev

# Deploy to your home directory (backs up existing config)
ccpm deploy python-dev local

# Deploy to a project directory
ccpm deploy python-dev local --project ./my-repo

# Deploy into a Docker container
ccpm deploy docker-deploy "docker my-container"

# Deploy via SSH
ccpm deploy python-dev "ssh user@devbox"
```

## CLI Reference

### `ccpm build <profile> [-o DIR] [--var KEY=VALUE] [--session FILE] [-v]`

Compile a profile into resolved config files. Outputs to a temp directory by default, or specify `--output-dir`.

```
$ ccpm build python-dev
Resolved chain: base-readonly -> git-permissions -> edit-permissions -> python-dev
  + .claude/settings.json
  + CLAUDE.md
  + .env.claude

4 files written to /tmp/ccpm-build-xxxxx
```

### `ccpm deploy <profile> <target> [--project DIR] [--var KEY=VALUE] [--session FILE] [--dry-run] [--no-backup] [-v]`

Build and deploy a profile to a target.

| Target | Example | Description |
|--------|---------|-------------|
| `local` | `ccpm deploy prof local` | Deploy to `~/.claude/` (or `--project` dir) |
| `docker CONTAINER` | `ccpm deploy prof "docker my-ctr"` | `docker cp` into a running container |
| `ssh USER@HOST` | `ccpm deploy prof "ssh user@box"` | `rsync` to a remote system |
| `dir PATH` | `ccpm deploy prof ./output` | Write to any directory |

The `--dry-run` flag shows what would change without writing. Existing configs are backed up to `.ccpm-backups/` unless `--no-backup` is passed.

### `ccpm list`

Show all available profiles from the search path.

```
$ ccpm list
┌──────────────┬──────────────────────────┬────────────────────────────────┐
│ Name         │ Description              │ Path                           │
├──────────────┼──────────────────────────┼────────────────────────────────┤
│ base-readonly│ Safe read-only defaults  │ ~/.claude/profiles/base-re...  │
│ python-dev   │ Python development       │ ~/.claude/profiles/python-...  │
└──────────────┴──────────────────────────┴────────────────────────────────┘
```

### `ccpm validate <profile>`

Check syntax, references, and cycle detection without building.

### `ccpm show <profile> [-s SECTION] [-v]`

Print the fully resolved merged config as JSON. Use `--section` to drill into a subtree:

```bash
ccpm show python-dev --section settings.permissions
```

### `ccpm diff <profile_a> <profile_b>`

Compare two resolved profiles as a unified diff.

### `ccpm init [--output FILE] [--name NAME] [--source-dir DIR]`

Reverse-engineer an existing Claude Code configuration into a TOML profile. Reads `settings.json`, `CLAUDE.md`, `.mcp.json`, and scans for skills/commands/agents.

```bash
# Print to stdout
ccpm init --source-dir ~/.claude

# Write to file
ccpm init --output my-profile.toml --name my-config
```

### Global Options

`--profile-path DIR` adds extra directories to the profile search path. Can be specified multiple times.

```bash
ccpm --profile-path ./team-profiles build team-base
```

## Profile Format

Profiles are TOML files. Every profile must have a `[profile]` section with at least a `name`.

### `[profile]` - Metadata

```toml
[profile]
name = "my-profile"
description = "What this profile does"
extends = ["base-readonly", "git-permissions"]  # optional inheritance chain
```

### `[settings]` - Claude Code Settings

Maps directly to `.claude/settings.json`. Any key that Claude Code accepts can go here.

```toml
[settings]
model = "us.anthropic.claude-opus-4-6-v1[1m]"
effortLevel = "high"
cleanupPeriodDays = 9999999

[settings.permissions]
allow = [
    "Read",
    "Edit",
    "Bash(pytest:*)",
]
deny = [
    "Bash(rm -rf*)",
]
```

#### Hooks

Hooks use Claude Code's event names as TOML array-of-tables:

```toml
[[settings.hooks.PostToolUse]]
matcher = "Edit|Write"
commands = ["./format.sh"]

[[settings.hooks.SessionStart]]
commands = [".claude/hooks/session-start.sh"]
```

This emits the proper Claude Code hooks JSON format in `settings.json`.

#### Plugins and Marketplaces

```toml
[settings.enabledPlugins]
"pr-workflow@softmax-plugins" = true

[settings.extraKnownMarketplaces.softmax-plugins]
source = { source = "github", repo = "Metta-AI/softmax-plugins" }
```

### `[claude_md]` - CLAUDE.md Content

```toml
[claude_md]
strategy = "append"  # "append" (default) | "prepend" | "replace"
content = """
## Rules
1. Always run tests
2. Never force push
"""
# Or reference a file:
# file = "${REPO_ROOT}/CLAUDE.md"
```

When profiles chain, each `claude_md` entry is applied in order using its strategy.

### `[[mcp_servers]]` - MCP Server Configuration

```toml
[[mcp_servers]]
name = "github"
command = "gh"
args = ["mcp"]

[[mcp_servers]]
name = "custom-api"
type = "http"
url = "http://localhost:8080/mcp"
```

Servers are merged by `name` across profiles - if two profiles define a server with the same name, their configs are deep-merged.

### `[env]` - Environment Variables

```toml
[env]
CLAUDE_CODE_USE_BEDROCK = "1"
ANTHROPIC_MODEL = "us.anthropic.claude-opus-4-6-v1"
```

Emitted as `.env.claude` with `export KEY="VALUE"` lines.

#### Env File Loading

Pull variables from `.env` files (useful for gitignored secrets):

```toml
[env]
env_file = ".env"                          # single file
# env_files = [".env.defaults", ".env.local"]  # multiple (later overrides earlier)
EXTRA_VAR = "inline-value"                 # inline vars override file-loaded vars
```

### `[[credentials]]` - Credential Management

Declare credentials that are resolved at build time:

```toml
[[credentials]]
name = "anthropic-api-key"
env_var = "ANTHROPIC_API_KEY"
description = "Anthropic API key for Claude Code"
source = "op read 'op://Dev/Anthropic/api-key'"  # optional: 1Password, AWS SSM, etc.
optional = false  # default: required
```

Resolution order:
1. `--var` CLI overrides
2. OS environment variables
3. `source` command (if provided)
4. Error if required and not found

Resolved credentials are emitted into the `env` section (and thus `.env.claude`).

### `[shell]` - Shell Configuration

```toml
[shell]
strategy = "append"  # "append" | "prepend" | "replace"
content = """
export PATH="$HOME/.local/bin:$PATH"
alias cc='claude'
"""
# Or reference a file:
# file = "./shell-setup.sh"
```

Emitted as `.bashrc.d/ccpm.sh`. Shell entries from parent profiles chain using the specified strategy.

### `[session]` - Session Log Deployment

Deploy a session log so Claude can resume a prior conversation in the target environment. A warning is injected at the end of the session to alert Claude that the environment may have changed.

```toml
[session]
log = "../sessions/my-session.jsonl"
# Optional: override where the session is placed (defaults to cwd from the log)
# project_dir = "/workspace/my-project"
# Optional: custom warning message (default warns about environment changes)
# warning = "You are now running in a Docker container. Check your tools."
```

The session JSONL is copied to `.claude/projects/<project-hash>/` matching Claude Code's expected layout. A resume helper script is generated at `.claude/ccpm-resume.sh`.

You can also pass a session log via the CLI without putting it in the profile:

```bash
ccpm build python-dev --session ~/.claude/projects/-Users-me/abc123.jsonl
ccpm deploy docker-deploy "docker my-ctr" --session ./saved-session.jsonl
```

After deploying, resume in the target environment:

```bash
# Using the generated script
.claude/ccpm-resume.sh

# Or directly
claude --resume <session-id>
```

The default warning injected into the session:

> WARNING TO CLAUDE: Your instance has been moved and may be in an incompatible environment or have completely new CLAUDE.md's, SKILL's, permissions, and more. The session history above is from a previous environment. Verify your current environment before making assumptions based on prior context.

### `[[skills]]`, `[[commands]]`, `[[agents]]`, `[[hook_scripts]]` - File Assets

Copy files/directories into the output:

```toml
[[skills]]
source = "${REPO_ROOT}/skills/my-skill"  # directory with SKILL.md

[[commands]]
source = "${HOME}/.claude/commands/todo.md"

[[agents]]
source = "${REPO_ROOT}/agents/reviewer.md"

[[hook_scripts]]
source = "${REPO_ROOT}/.claude/hooks/session-start.sh"
target = ".claude/hooks/session-start.sh"
```

Skills, commands, and agents can also be defined inline:

```toml
[[commands]]
name = "review.md"
content = """
Review the current PR for correctness and style.
"""
```

## Merge Semantics

The core operation is **step-by-step deep recursive merge** through the extends chain:

```
acc = {}
acc = deep_merge(acc, base)         # apply base profile
acc = deep_merge(acc, middle)       # apply middle on top
acc = deep_merge(acc, leaf)         # apply leaf on top
```

At every level of nesting:
- **Dicts** merge recursively (keys combine)
- **Lists** union with deduplication (items accumulate)
- **Scalars** are replaced by the child's value
- Child profiles only need to specify what they change

### `!replace:` Escape Hatch

To fully wipe a parent's subtree instead of merging into it:

```toml
# Wipe parent's permissions entirely, start fresh
[settings."!replace:permissions"]
allow = ["Read"]
# parent's allow and deny lists are gone
```

## Environment Variables

`${VAR}` and `${VAR:-default}` syntax is expanded at compile time in all string values:

```toml
[env]
API_URL = "${MY_HOST:-localhost}:8080"

[[skills]]
source = "${REPO_ROOT}/skills/my-skill"
```

Variables are resolved from:
1. `--var` CLI overrides (`ccpm build prof --var REPO_ROOT=/code`)
2. OS environment

Unresolved variables without defaults produce a clear error with a hint to set the variable.

## Profile Search Path

Profiles are discovered in order from:
1. `$CLAUDE_PROFILE_PATH` (colon-separated directories)
2. `~/.claude/profiles/`
3. `./.claude/profiles/` (current directory)

Additional directories can be added with `--profile-path`.

You can also pass an absolute path to a TOML file directly:

```bash
ccpm build /path/to/my-profile.toml
```

## Output Structure

A compiled profile produces:

```
output/
  .claude/
    settings.json          # merged settings with hooks in Claude Code format
    skills/                # copied skill directories
    commands/              # copied command files
    agents/                # copied agent files
    hooks/                 # copied hook scripts
    projects/              # session logs (if [session] is configured)
      <project-hash>/
        <session-id>.jsonl # session log with warning injected
    ccpm-resume.sh         # helper script to resume session
  .mcp.json                # MCP server configuration
  CLAUDE.md                # chained claude_md content
  .env.claude              # environment variables (sourceable)
  .bashrc.d/
    ccpm.sh                # shell configuration
```

## Examples

The `examples/profiles/` directory contains profiles demonstrating every feature:

| Profile | What it shows |
|---------|---------------|
| `base-readonly.toml` | Safe read-only defaults |
| `git-permissions.toml` | Git/GitHub CLI access |
| `edit-permissions.toml` | File editing permissions |
| `python-dev.toml` | Multi-level extends, model override |
| `full-featured.toml` | Every feature: hooks, plugins, MCP, skills, agents |
| `with-credentials.toml` | Credential declarations with source commands |
| `with-env-file.toml` | Loading variables from `.env` files |
| `with-shell.toml` | Shell config (PATH, aliases, nvm) |
| `docker-deploy.toml` | Full container deployment profile |
| `replace-example.toml` | `!replace:` escape hatch |
| `json-ref.toml` | External JSON file references |
| `with-session.toml` | Session log deployment for cross-environment resumption |
| `env-vars.toml` | `${VAR:-default}` expansion |

## Development

```bash
git clone https://github.com/Metta-AI/ccpm.git
cd ccpm
uv sync
uv run pytest -v
```

193 tests covering deep merge, env expansion, chain resolution, compilation, emission, round-trips, CLI, discovery, backup, credentials, shell config, env file loading, and session log deployment.

## License

MIT
