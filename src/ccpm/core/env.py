"""Environment variable resolution in profile values."""

from __future__ import annotations

import os
import re
from typing import Any

# Matches ${VAR} and ${VAR:-default}
_ENV_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


class UnresolvedEnvVar(Exception):
    def __init__(self, var_name: str, context: str = ""):
        self.var_name = var_name
        self.context = context
        msg = f"Unresolved variable ${{{var_name}}}"
        if context:
            msg += f" in {context}"
        msg += f"\n  Hint: Set {var_name} in your environment or pass --var {var_name}=/path/to/value"
        super().__init__(msg)


def expand_env(
    data: Any,
    overrides: dict[str, str] | None = None,
    context: str = "",
) -> Any:
    """Recursively expand ${VAR} and ${VAR:-default} in all string values.

    Uses overrides first, then os.environ. Raises UnresolvedEnvVar on miss.
    """
    env = {**os.environ, **(overrides or {})}
    return _expand(data, env, context)


def _expand(data: Any, env: dict[str, str], context: str) -> Any:
    if isinstance(data, str):
        return _expand_string(data, env, context)
    if isinstance(data, dict):
        return {
            _expand_string(k, env, context) if isinstance(k, str) else k: _expand(v, env, f"{context}.{k}" if context else str(k))
            for k, v in data.items()
        }
    if isinstance(data, list):
        return [_expand(item, env, f"{context}[{i}]") for i, item in enumerate(data)]
    return data


def _expand_string(s: str, env: dict[str, str], context: str) -> str:
    def replacer(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2)
        if var_name in env:
            return env[var_name]
        if default is not None:
            return default
        raise UnresolvedEnvVar(var_name, context)

    return _ENV_PATTERN.sub(replacer, s)
