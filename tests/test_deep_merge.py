"""Tests for the deep_merge function — the core of ccpm."""

from ccpm.core.deep_merge import deep_merge


class TestScalarMerge:
    def test_new_key(self):
        target = {"a": 1}
        deep_merge(target, {"b": 2})
        assert target == {"a": 1, "b": 2}

    def test_overwrite_scalar(self):
        target = {"model": "haiku"}
        deep_merge(target, {"model": "opus"})
        assert target["model"] == "opus"

    def test_overwrite_preserves_siblings(self):
        target = {"model": "haiku", "effort": "low"}
        deep_merge(target, {"model": "opus"})
        assert target == {"model": "opus", "effort": "low"}

    def test_none_overwrites(self):
        target = {"a": 1}
        deep_merge(target, {"a": None})
        assert target["a"] is None

    def test_type_change_source_wins(self):
        target = {"a": "string"}
        deep_merge(target, {"a": 42})
        assert target["a"] == 42


class TestDictMerge:
    def test_nested_dicts_recurse(self):
        target = {"settings": {"model": "haiku", "effort": "low"}}
        deep_merge(target, {"settings": {"model": "opus"}})
        assert target == {"settings": {"model": "opus", "effort": "low"}}

    def test_deeply_nested(self):
        target = {"a": {"b": {"c": {"d": 1, "e": 2}}}}
        deep_merge(target, {"a": {"b": {"c": {"d": 99}}}})
        assert target["a"]["b"]["c"] == {"d": 99, "e": 2}

    def test_new_nested_key(self):
        target = {"settings": {"model": "haiku"}}
        deep_merge(target, {"settings": {"permissions": {"allow": ["Read"]}}})
        assert target == {
            "settings": {"model": "haiku", "permissions": {"allow": ["Read"]}}
        }

    def test_empty_source_dict_no_change(self):
        target = {"a": {"b": 1}}
        deep_merge(target, {"a": {}})
        assert target == {"a": {"b": 1}}

    def test_empty_target_dict_gets_filled(self):
        target = {"a": {}}
        deep_merge(target, {"a": {"b": 1}})
        assert target == {"a": {"b": 1}}


class TestListMerge:
    def test_list_union(self):
        target = {"allow": ["Read", "Glob"]}
        deep_merge(target, {"allow": ["Edit", "Write"]})
        assert target["allow"] == ["Read", "Glob", "Edit", "Write"]

    def test_list_deduplicates(self):
        target = {"allow": ["Read", "Glob"]}
        deep_merge(target, {"allow": ["Read", "Edit"]})
        assert target["allow"] == ["Read", "Glob", "Edit"]

    def test_list_preserves_order(self):
        target = {"items": [1, 2, 3]}
        deep_merge(target, {"items": [4, 2, 5]})
        assert target["items"] == [1, 2, 3, 4, 5]

    def test_list_with_dicts(self):
        target = {"servers": [{"name": "a"}]}
        deep_merge(target, {"servers": [{"name": "b"}]})
        assert target["servers"] == [{"name": "a"}, {"name": "b"}]

    def test_list_with_duplicate_dicts(self):
        target = {"servers": [{"name": "a"}]}
        deep_merge(target, {"servers": [{"name": "a"}]})
        assert target["servers"] == [{"name": "a"}]

    def test_empty_source_list(self):
        target = {"items": [1, 2]}
        deep_merge(target, {"items": []})
        assert target["items"] == [1, 2]

    def test_empty_target_list(self):
        target = {"items": []}
        deep_merge(target, {"items": [1, 2]})
        assert target["items"] == [1, 2]


class TestReplacePrefix:
    def test_replace_wipes_dict(self):
        target = {"permissions": {"allow": ["Read", "Glob"], "deny": ["Bash(rm*)"]}}
        deep_merge(target, {"!replace:permissions": {"allow": ["Edit"]}})
        assert target["permissions"] == {"allow": ["Edit"]}

    def test_replace_wipes_list(self):
        target = {"items": [1, 2, 3]}
        deep_merge(target, {"!replace:items": [99]})
        assert target["items"] == [99]

    def test_replace_wipes_scalar(self):
        target = {"model": "haiku"}
        deep_merge(target, {"!replace:model": "opus"})
        assert target["model"] == "opus"

    def test_replace_nested(self):
        target = {"settings": {"permissions": {"allow": ["Read"], "deny": ["Bash(rm*)"]}}}
        deep_merge(
            target,
            {"settings": {"!replace:permissions": {"allow": ["Edit"]}}},
        )
        assert target["settings"]["permissions"] == {"allow": ["Edit"]}


class TestIdempotency:
    def test_same_merge_twice_is_idempotent(self):
        source = {"settings": {"model": "opus", "permissions": {"allow": ["Read", "Edit"]}}}
        target = {}
        deep_merge(target, source)
        snapshot = {k: v for k, v in target.items()}  # shallow copy for comparison
        deep_merge(target, source)
        assert target == snapshot

    def test_empty_merge_is_noop(self):
        target = {"a": 1, "b": [2], "c": {"d": 3}}
        original = {"a": 1, "b": [2], "c": {"d": 3}}
        deep_merge(target, {})
        assert target == original


class TestComplexScenarios:
    def test_permissions_deep_merge(self):
        """Simulates merging two Claude Code settings.json permission sets."""
        base = {
            "permissions": {
                "allow": ["Read", "Glob", "Grep", "WebFetch"],
                "deny": ["Bash(rm -rf*)"],
            },
            "model": "haiku",
            "effortLevel": "medium",
        }
        overlay = {
            "permissions": {
                "allow": ["Edit", "Write", "Bash(pytest:*)"],
            },
            "model": "opus",
        }
        deep_merge(base, overlay)
        assert base == {
            "permissions": {
                "allow": ["Read", "Glob", "Grep", "WebFetch", "Edit", "Write", "Bash(pytest:*)"],
                "deny": ["Bash(rm -rf*)"],
            },
            "model": "opus",
            "effortLevel": "medium",
        }

    def test_three_layer_merge(self):
        """Simulates a 3-profile chain merge."""
        acc = {}
        deep_merge(acc, {"settings": {"permissions": {"allow": ["Read"]}, "effort": "low"}})
        deep_merge(acc, {"settings": {"permissions": {"allow": ["Glob"]}}})
        deep_merge(acc, {"settings": {"permissions": {"allow": ["Edit"]}, "effort": "high"}})
        assert acc == {
            "settings": {
                "permissions": {"allow": ["Read", "Glob", "Edit"]},
                "effort": "high",
            }
        }

    def test_hooks_merge(self):
        """Hooks from different profiles accumulate."""
        acc = {}
        deep_merge(acc, {"hooks": {"SessionStart": [{"commands": ["echo a"]}]}})
        deep_merge(acc, {"hooks": {"PostToolUse": [{"commands": ["fmt.sh"]}]}})
        deep_merge(acc, {"hooks": {"SessionStart": [{"commands": ["echo b"]}]}})
        assert "SessionStart" in acc["hooks"]
        assert "PostToolUse" in acc["hooks"]
        # SessionStart should have both hook groups via list union
        assert len(acc["hooks"]["SessionStart"]) == 2
