"""Pydantic models for TOML profile validation."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProfileMeta(BaseModel):
    name: str
    description: str = ""
    extends: list[str] = Field(default_factory=list)


class HookGroup(BaseModel):
    matcher: str | None = None
    commands: list[str]


class ClaudeMd(BaseModel):
    strategy: Literal["append", "prepend", "replace"] = "append"
    content: str | None = None
    file: str | None = None


class McpServer(BaseModel):
    name: str
    type: str | None = None  # "stdio" (default), "http", "sse"
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)
    env: dict[str, str] = Field(default_factory=dict)


class FileAsset(BaseModel):
    source: str
    target: str | None = None  # relative path in output; inferred from source if absent
    name: str | None = None  # for inline content
    content: str | None = None


class Profile(BaseModel):
    """Validated representation of a parsed TOML profile."""

    profile: ProfileMeta
    settings: dict[str, Any] = Field(default_factory=dict)
    claude_md: ClaudeMd | None = None
    mcp_servers: list[McpServer] = Field(default_factory=list)
    skills: list[FileAsset] = Field(default_factory=list)
    commands: list[FileAsset] = Field(default_factory=list)
    agents: list[FileAsset] = Field(default_factory=list)
    hook_scripts: list[FileAsset] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_toml_dict(cls, data: dict[str, Any]) -> Profile:
        """Construct a Profile from a raw TOML-parsed dict.

        Handles the fact that TOML uses underscores in keys but
        the parsed dict structure matches the model fields.
        """
        return cls.model_validate(data)
