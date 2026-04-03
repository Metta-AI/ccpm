"""Tests for shell configuration emission."""

from ccpm.core.compiler import compile_profile
from ccpm.emit import emit_all
from ccpm.emit.shell import emit_shell


class TestEmitShell:
    def test_basic_emit(self, tmp_path):
        entries = [{"strategy": "append", "content": 'export PATH="$HOME/.local/bin:$PATH"'}]
        path = emit_shell(entries, tmp_path)
        assert path is not None
        text = path.read_text()
        assert 'export PATH="$HOME/.local/bin:$PATH"' in text

    def test_location(self, tmp_path):
        entries = [{"strategy": "append", "content": "echo hi"}]
        path = emit_shell(entries, tmp_path)
        assert path == tmp_path / ".bashrc.d" / "ccpm.sh"

    def test_has_header(self, tmp_path):
        entries = [{"strategy": "append", "content": "echo hi"}]
        path = emit_shell(entries, tmp_path)
        text = path.read_text()
        assert text.startswith("#!/bin/bash")
        assert "ccpm" in text

    def test_empty_returns_none(self, tmp_path):
        assert emit_shell([], tmp_path) is None

    def test_append_strategy(self, tmp_path):
        entries = [
            {"strategy": "append", "content": "# First block"},
            {"strategy": "append", "content": "# Second block"},
        ]
        path = emit_shell(entries, tmp_path)
        text = path.read_text()
        assert text.index("First block") < text.index("Second block")

    def test_replace_strategy(self, tmp_path):
        entries = [
            {"strategy": "append", "content": "# Should be gone"},
            {"strategy": "replace", "content": "# Only this"},
        ]
        path = emit_shell(entries, tmp_path)
        text = path.read_text()
        assert "Should be gone" not in text
        assert "Only this" in text

    def test_prepend_strategy(self, tmp_path):
        entries = [
            {"strategy": "append", "content": "# After"},
            {"strategy": "prepend", "content": "# Before"},
        ]
        path = emit_shell(entries, tmp_path)
        text = path.read_text()
        assert text.index("Before") < text.index("After")

    def test_file_reference(self, tmp_path, examples_dir):
        entries = [{"strategy": "replace", "file": str(examples_dir / "shell" / "container-setup.sh")}]
        path = emit_shell(entries, tmp_path)
        text = path.read_text()
        assert "Container shell setup" in text
        assert "NVM_DIR" in text


class TestShellInProfile:
    def test_shell_from_profile(self, search_path, tmp_path):
        compiled = compile_profile("with-shell", search_path)
        written = emit_all(compiled, tmp_path / "out")
        paths = {p.name for p in written}
        assert "ccpm.sh" in paths
        text = (tmp_path / "out" / ".bashrc.d" / "ccpm.sh").read_text()
        assert "PATH" in text
        assert "alias cc=" in text

    def test_shell_file_ref_from_profile(self, search_path, tmp_path, examples_dir):
        compiled = compile_profile(
            "shell-file-ref",
            search_path,
            env_overrides={"EXAMPLES_DIR": str(examples_dir)},
        )
        written = emit_all(compiled, tmp_path / "out")
        text = (tmp_path / "out" / ".bashrc.d" / "ccpm.sh").read_text()
        assert "Container shell setup" in text

    def test_shell_chains_across_profiles(self, tmp_path):
        """Shell config from parent and child profiles should chain."""
        base = tmp_path / "profiles" / "shell-base.toml"
        base.parent.mkdir(parents=True)
        base.write_text('''
[profile]
name = "shell-base"

[shell]
strategy = "append"
content = "export BASE_VAR=1"
''')
        child = tmp_path / "profiles" / "shell-child.toml"
        child.write_text('''
[profile]
name = "shell-child"
extends = ["shell-base"]

[shell]
strategy = "append"
content = "export CHILD_VAR=2"
''')
        compiled = compile_profile(str(child), [tmp_path / "profiles"])
        written = emit_all(compiled, tmp_path / "out")
        text = (tmp_path / "out" / ".bashrc.d" / "ccpm.sh").read_text()
        assert "BASE_VAR" in text
        assert "CHILD_VAR" in text
        assert text.index("BASE_VAR") < text.index("CHILD_VAR")
