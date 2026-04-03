"""Round-trip tests: init -> build -> compare."""

import json
from pathlib import Path

from ccpm.core.compiler import compile_profile
from ccpm.emit import emit_all
from ccpm.util.init import init_profile


class TestRoundTrip:
    def test_settings_roundtrip(self, tmp_path):
        """Create a settings.json, init a profile from it, build, compare."""
        # Create a source directory with settings.json
        source = tmp_path / "source"
        source.mkdir()
        (source / ".claude").mkdir()

        original_settings = {
            "permissions": {
                "allow": ["Read", "Glob", "Grep", "WebFetch"],
                "deny": ["Bash(rm -rf*)"],
            },
            "model": "opus",
            "effortLevel": "high",
            "cleanupPeriodDays": 9999,
        }
        (source / ".claude" / "settings.json").write_text(
            json.dumps(original_settings, indent=2)
        )

        # Init a profile from the source
        profile_path = tmp_path / "profiles" / "test.toml"
        init_profile(source_dir=source, output_path=profile_path, profile_name="test")

        # Build the profile
        output = tmp_path / "output"
        compiled = compile_profile(str(profile_path), [])
        emit_all(compiled, output)

        # Compare
        rebuilt = json.loads((output / ".claude" / "settings.json").read_text())
        assert rebuilt == original_settings

    def test_hooks_roundtrip(self, tmp_path):
        """Hooks should survive init -> build."""
        source = tmp_path / "source"
        source.mkdir()
        (source / ".claude").mkdir()

        original = {
            "hooks": {
                "PostToolUse": [
                    {
                        "matcher": "Edit|Write",
                        "hooks": [
                            {"type": "command", "command": "format.sh"},
                            {"type": "command", "command": "lint.sh"},
                        ],
                    }
                ],
                "SessionStart": [
                    {
                        "hooks": [
                            {"type": "command", "command": "echo start"},
                        ]
                    }
                ],
            }
        }
        (source / ".claude" / "settings.json").write_text(json.dumps(original, indent=2))

        profile_path = tmp_path / "profiles" / "test.toml"
        init_profile(source_dir=source, output_path=profile_path, profile_name="test")

        output = tmp_path / "output"
        compiled = compile_profile(str(profile_path), [])
        emit_all(compiled, output)

        rebuilt = json.loads((output / ".claude" / "settings.json").read_text())
        assert rebuilt == original

    def test_claude_md_roundtrip(self, tmp_path):
        """CLAUDE.md content should survive init -> build."""
        source = tmp_path / "source"
        source.mkdir()

        content = "# My Project\n\nImportant rules here."
        (source / "CLAUDE.md").write_text(content)

        profile_path = tmp_path / "profiles" / "test.toml"
        init_profile(source_dir=source, output_path=profile_path, profile_name="test")

        output = tmp_path / "output"
        compiled = compile_profile(str(profile_path), [])
        emit_all(compiled, output)

        rebuilt = (output / "CLAUDE.md").read_text().strip()
        assert rebuilt == content

    def test_full_roundtrip(self, tmp_path):
        """Full config with settings + CLAUDE.md + env."""
        source = tmp_path / "source"
        source.mkdir()
        (source / ".claude").mkdir()

        settings = {"model": "opus", "permissions": {"allow": ["Read"]}}
        (source / ".claude" / "settings.json").write_text(json.dumps(settings, indent=2))
        (source / "CLAUDE.md").write_text("# Rules\nBe concise.\n")
        (source / ".env.claude").write_text('export KEY="val"\nexport OTHER="123"\n')

        profile_path = tmp_path / "profiles" / "test.toml"
        init_profile(source_dir=source, output_path=profile_path, profile_name="test")

        output = tmp_path / "output"
        compiled = compile_profile(str(profile_path), [])
        emit_all(compiled, output)

        # Settings match
        rebuilt_settings = json.loads((output / ".claude" / "settings.json").read_text())
        assert rebuilt_settings == settings

        # CLAUDE.md matches
        assert "Be concise" in (output / "CLAUDE.md").read_text()

        # Env file matches
        env_text = (output / ".env.claude").read_text()
        assert 'export KEY="val"' in env_text
        assert 'export OTHER="123"' in env_text
