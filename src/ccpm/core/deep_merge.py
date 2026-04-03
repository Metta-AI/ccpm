"""The deep_merge function — central to everything in ccpm."""

from __future__ import annotations

from typing import Any

REPLACE_PREFIX = "!replace:"


def deep_merge(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Recursively deep-merge source into target, mutating target in place.

    Rules:
    - Dicts: recurse (keys from both survive)
    - Lists: union (deduplicate, preserve order)
    - Scalars: source wins (last writer wins)
    - Keys prefixed with "!replace:" wipe the target's value entirely
    """
    for key, value in source.items():
        if key.startswith(REPLACE_PREFIX):
            real_key = key[len(REPLACE_PREFIX) :]
            target[real_key] = value
        elif isinstance(value, dict) and isinstance(target.get(key), dict):
            deep_merge(target[key], value)
        elif isinstance(value, list) and isinstance(target.get(key), list):
            _list_union(target[key], value)
        else:
            target[key] = value
    return target


def _list_union(target: list, source: list) -> None:
    """Append items from source that aren't already in target. Preserves order."""
    # For unhashable items (dicts), fall back to equality check
    hashable = all(_is_hashable(item) for item in target)
    if hashable:
        seen = set(target)
        for item in source:
            if _is_hashable(item) and item not in seen:
                target.append(item)
                seen.add(item)
            elif not _is_hashable(item) and item not in target:
                target.append(item)
    else:
        for item in source:
            if item not in target:
                target.append(item)


def _is_hashable(obj: Any) -> bool:
    try:
        hash(obj)
        return True
    except TypeError:
        return False
