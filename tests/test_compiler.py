"""Tests for the compiler — the full resolve -> expand -> merge pipeline."""

import json

import pytest

from ccpm.core.compiler import compile_profile


class TestBasicCompilation:
    def test_minimal_profile(self, search_path):
        compiled = compile_profile("minimal", search_path)
        assert compiled.chain_names == ["minimal"]
        assert compiled.settings["permissions"]["allow"] == ["Read", "Glob", "Grep"]

    def test_chain_names(self, search_path):
        compiled = compile_profile("python-dev", search_path)
        assert compiled.chain_names == [
            "base-readonly",
            "git-permissions",
            "edit-permissions",
            "python-dev",
        ]


class TestDeepMergeInChain:
    def test_permissions_accumulate(self, search_path):
        compiled = compile_profile("python-dev", search_path)
        allow = compiled.settings["permissions"]["allow"]
        # From base-readonly
        assert "Read" in allow
        assert "Glob" in allow
        assert "WebFetch" in allow
        # From git-permissions
        assert "Bash(git status:*)" in allow
        assert "Bash(gh pr view:*)" in allow
        # From edit-permissions
        assert "Edit" in allow
        assert "Write" in allow
        # From python-dev itself
        assert "Bash(pytest:*)" in allow
        assert "Bash(ruff check:*)" in allow

    def test_scalar_last_writer_wins(self, search_path):
        compiled = compile_profile("python-dev", search_path)
        # base-readonly sets medium, python-dev overrides to high
        assert compiled.settings["effortLevel"] == "high"
        # python-dev sets model, base-readonly doesn't
        assert compiled.settings["model"] == "us.anthropic.claude-opus-4-6-v1[1m]"

    def test_untouched_keys_survive(self, search_path):
        compiled = compile_profile("python-dev", search_path)
        # cleanupPeriodDays is only set by base-readonly
        assert compiled.settings["cleanupPeriodDays"] == 30

    def test_env_accumulates(self, search_path):
        compiled = compile_profile("python-dev", search_path)
        # base-readonly sets CLAUDE_CODE_USE_BEDROCK
        assert compiled.env["CLAUDE_CODE_USE_BEDROCK"] == "1"

    def test_diamond_merge(self, search_path):
        compiled = compile_profile("diamond-top", search_path)
        allow = compiled.settings["permissions"]["allow"]
        # diamond-a: Read, diamond-b: Glob, diamond-c: Grep, diamond-top: WebFetch
        assert "Read" in allow
        assert "Glob" in allow
        assert "Grep" in allow
        assert "WebFetch" in allow


class TestReplacePrefix:
    def test_replace_wipes_parent_permissions(self, search_path):
        compiled = compile_profile("replace-example", search_path)
        # replace-example extends base-readonly but uses !replace:permissions
        assert compiled.settings["permissions"] == {"allow": ["Read"]}
        # No deny, no WebFetch, no Glob — parent's perms are wiped

    def test_replace_preserves_sibling_keys(self, search_path):
        compiled = compile_profile("replace-example", search_path)
        # model is set by replace-example, effortLevel from base-readonly
        assert compiled.settings["model"] == "us.anthropic.claude-opus-4-6-v1[1m]"
        assert compiled.settings["effortLevel"] == "medium"


class TestHooks:
    def test_hooks_in_compiled(self, search_path, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        hooks = compiled.settings["hooks"]
        assert "SessionStart" in hooks
        assert "PostToolUse" in hooks
        assert "UserPromptSubmit" in hooks

    def test_hook_commands_present(self, search_path, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        session_start = compiled.settings["hooks"]["SessionStart"]
        assert len(session_start) >= 1
        assert "commands" in session_start[0]


class TestMcpServers:
    def test_mcp_servers_collected(self, search_path, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        servers = compiled.mcp_servers
        assert "github" in servers
        assert "context7" in servers

    def test_mcp_server_fields(self, search_path, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        github = compiled.mcp_servers["github"]
        assert github["command"] == "gh"
        assert github["args"] == ["mcp"]


class TestClaudeMd:
    def test_claude_md_entries(self, search_path):
        compiled = compile_profile("python-dev", search_path)
        entries = compiled.claude_md_entries
        assert len(entries) >= 1
        assert entries[-1]["strategy"] == "append"
        assert "Python Conventions" in entries[-1]["content"]

    def test_claude_md_replace(self, search_path):
        compiled = compile_profile("claude-md-replace", search_path)
        entries = compiled.claude_md_entries
        # python-dev appends, claude-md-replace replaces
        strategies = [e["strategy"] for e in entries]
        assert "replace" in strategies


class TestFileAssets:
    def test_skills_collected(self, search_path, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        assert len(compiled.skills) >= 1
        assert any(str(examples_dir / "skills/my-skill") in s["source"] for s in compiled.skills)

    def test_commands_collected(self, search_path, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        assert len(compiled.commands) >= 1

    def test_agents_collected(self, search_path, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        assert len(compiled.agents) >= 1

    def test_hook_scripts_collected(self, search_path, examples_dir):
        compiled = compile_profile(
            "full-featured",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        assert len(compiled.hook_scripts) >= 1


class TestJsonFileRef:
    def test_json_file_loaded(self, search_path):
        compiled = compile_profile("json-ref", search_path)
        assert compiled.settings["model"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"
        assert "Read" in compiled.settings["permissions"]["allow"]

    def test_json_ref_chain_merges(self, search_path):
        compiled = compile_profile("json-ref-with-overrides", search_path)
        allow = compiled.settings["permissions"]["allow"]
        # From base-settings.json (via json-ref)
        assert "Read" in allow
        assert "Glob" in allow
        assert "Grep" in allow
        # From extra-settings.json (via json-ref-with-overrides)
        assert "Edit" in allow
        assert "Write" in allow
        assert "WebFetch" in allow

    def test_json_ref_scalar_override(self, search_path):
        compiled = compile_profile("json-ref-with-overrides", search_path)
        # extra-settings.json has opus, overriding haiku from base
        assert compiled.settings["model"] == "us.anthropic.claude-opus-4-6-v1[1m]"

    def test_json_ref_inline_override(self, search_path):
        compiled = compile_profile("json-ref-with-overrides", search_path)
        # effortLevel = "high" is inline in the TOML, overriding nothing from JSON
        assert compiled.settings["effortLevel"] == "high"

    def test_json_ref_untouched_survives(self, search_path):
        compiled = compile_profile("json-ref-with-overrides", search_path)
        # deny from base-settings.json should survive
        assert "Bash(rm -rf*)" in compiled.settings["permissions"]["deny"]
        # cleanupPeriodDays from base-settings.json
        assert compiled.settings["cleanupPeriodDays"] == 30


class TestEnvVarResolution:
    def test_default_values(self, search_path):
        compiled = compile_profile("env-vars", search_path)
        assert compiled.settings["model"] == "us.anthropic.claude-haiku-4-5-20251001-v1:0"

    def test_override_via_env(self, search_path):
        compiled = compile_profile(
            "env-vars",
            search_path,
            env_overrides={"CUSTOM_MODEL": "opus"},
        )
        assert compiled.settings["model"] == "opus"

    def test_home_expansion(self, search_path):
        import os

        compiled = compile_profile("env-vars", search_path)
        assert compiled.env["CUSTOM_VAR"] == f"{os.environ['HOME']}/.claude/custom"
