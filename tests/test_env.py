"""Tests for environment variable resolution."""

import os

import pytest

from ccpm.core.env import UnresolvedEnvVar, expand_env


class TestBasicExpansion:
    def test_simple_var(self):
        result = expand_env({"path": "${HOME}/test"}, overrides={"HOME": "/users/me"})
        assert result == {"path": "/users/me/test"}

    def test_multiple_vars_in_string(self):
        result = expand_env(
            {"path": "${BASE}/${SUB}/file"},
            overrides={"BASE": "/opt", "SUB": "config"},
        )
        assert result == {"path": "/opt/config/file"}

    def test_var_with_default(self):
        result = expand_env({"model": "${CUSTOM_MODEL:-haiku}"}, overrides={})
        assert result == {"model": "haiku"}

    def test_var_with_default_not_used_when_set(self):
        result = expand_env(
            {"model": "${CUSTOM_MODEL:-haiku}"},
            overrides={"CUSTOM_MODEL": "opus"},
        )
        assert result == {"model": "opus"}

    def test_empty_default(self):
        result = expand_env({"val": "${MISSING:-}"}, overrides={})
        assert result == {"val": ""}

    def test_no_vars_passthrough(self):
        result = expand_env({"plain": "no variables here"})
        assert result == {"plain": "no variables here"}


class TestNestedExpansion:
    def test_nested_dict(self):
        data = {"outer": {"inner": "${VAR}"}}
        result = expand_env(data, overrides={"VAR": "value"})
        assert result == {"outer": {"inner": "value"}}

    def test_list_expansion(self):
        data = {"items": ["${A}", "static", "${B}"]}
        result = expand_env(data, overrides={"A": "x", "B": "y"})
        assert result == {"items": ["x", "static", "y"]}

    def test_deeply_nested(self):
        data = {"a": {"b": {"c": {"d": "${V}"}}}}
        result = expand_env(data, overrides={"V": "deep"})
        assert result["a"]["b"]["c"]["d"] == "deep"

    def test_dict_key_expansion(self):
        data = {"${KEY}": "value"}
        result = expand_env(data, overrides={"KEY": "resolved"})
        assert result == {"resolved": "value"}


class TestUnresolved:
    def test_unresolved_raises(self):
        with pytest.raises(UnresolvedEnvVar) as exc_info:
            expand_env({"path": "${NONEXISTENT_VAR_12345}"})
        assert "NONEXISTENT_VAR_12345" in str(exc_info.value)

    def test_unresolved_includes_context(self):
        with pytest.raises(UnresolvedEnvVar) as exc_info:
            expand_env({"path": "${MISSING}"}, context="test-profile")
        assert "test-profile" in str(exc_info.value)

    def test_unresolved_hint_message(self):
        with pytest.raises(UnresolvedEnvVar) as exc_info:
            expand_env({"path": "${NOPE}"})
        assert "--var" in str(exc_info.value)


class TestOsEnvironment:
    def test_reads_os_environ(self):
        result = expand_env({"home": "${HOME}"})
        assert result == {"home": os.environ["HOME"]}

    def test_overrides_take_precedence(self):
        result = expand_env(
            {"home": "${HOME}"},
            overrides={"HOME": "/custom/home"},
        )
        assert result == {"home": "/custom/home"}


class TestNonStringPassthrough:
    def test_int_passthrough(self):
        assert expand_env({"count": 42}) == {"count": 42}

    def test_bool_passthrough(self):
        assert expand_env({"flag": True}) == {"flag": True}

    def test_none_passthrough(self):
        assert expand_env({"val": None}) == {"val": None}

    def test_mixed_types(self):
        data = {"str": "${V}", "int": 1, "list": ["${V}", 2], "bool": False}
        result = expand_env(data, overrides={"V": "x"})
        assert result == {"str": "x", "int": 1, "list": ["x", 2], "bool": False}
