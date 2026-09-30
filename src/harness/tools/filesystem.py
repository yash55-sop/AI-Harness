"""Workspace-scoped UTF-8 filesystem tools."""

from __future__ import annotations

import os
import stat
from copy import copy
from pathlib import Path
from typing import Any

from harness.exceptions import ConfigurationError, ToolError
from harness.tools.base import Tool


class WorkspaceTool(Tool):
    """Share resolved-path boundary checks and agent workspace binding."""

    def __init__(self, workspace: str | Path | None = None) -> None:
        self.workspace = Path(workspace if workspace is not None else Path.cwd()).resolve()
        if not self.workspace.is_dir():
            raise ConfigurationError("Workspace must be an existing directory")

    def bind_workspace(self, workspace: Path) -> WorkspaceTool:
        """Copy rather than mutate a tool that another agent may also use."""
        if not workspace.is_dir():
            raise ConfigurationError("Workspace must be an existing directory")
        bound = copy(self)
        bound.workspace = workspace.resolve()
        return bound

    def resolve_path(self, path: str) -> Path:
        try:
            requested = Path(path)
            resolved = (
                requested if requested.is_absolute() else self.workspace / requested
            ).resolve()
            resolved.relative_to(self.workspace)
            # NTFS alternate streams can address data outside a normal file name.
            if os.name == "nt" and any(
                ":" in part for part in resolved.relative_to(self.workspace).parts
            ):
                raise ValueError("Alternate data streams are unsupported")
            return resolved
        except (OSError, ValueError, RuntimeError):
            raise ToolError("Path must resolve inside the configured workspace") from None


class ReadFile(WorkspaceTool):
    name = "read_file"
    description = "Read a UTF-8 text file inside the workspace"

    def __init__(self, workspace: str | Path | None = None, *, max_bytes: int = 1_000_000) -> None:
        super().__init__(workspace)
        if type(max_bytes) is not int or max_bytes <= 0:
            raise ConfigurationError("ReadFile max_bytes must be a positive integer")
        self.max_bytes = max_bytes

    def run(self, path: str) -> str:
        target = self.resolve_path(path)
        try:
            if not stat.S_ISREG(target.stat().st_mode):
                raise ToolError("ReadFile requires a regular file")
            with target.open("rb") as file:
                content = file.read(self.max_bytes + 1)
            if len(content) > self.max_bytes:
                raise ToolError("File exceeds ReadFile max_bytes")
            return content.decode("utf-8")
        except (OSError, UnicodeError):
            raise ToolError("Cannot read file as UTF-8") from None


class WriteFile(WorkspaceTool):
    name = "write_file"
    description = "Create or replace a UTF-8 text file inside the workspace"

    def run(self, path: str, content: str) -> dict[str, Any]:
        target = self.resolve_path(path)
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            # Check again after creating parent directories, before opening the file.
            target = self.resolve_path(path)
            if target.exists() and not stat.S_ISREG(target.stat().st_mode):
                raise ToolError("WriteFile requires a regular file")
            # Reject hard links: replacing their contents could alter an outside alias.
            if target.exists() and target.stat().st_nlink > 1:
                raise ToolError("WriteFile does not overwrite hard-linked files")
            encoded = content.encode("utf-8")
            target.write_bytes(encoded)
            return {
                "path": target.relative_to(self.workspace).as_posix(),
                "bytes_written": len(encoded),
            }
        except (OSError, UnicodeError):
            raise ToolError("Cannot write file in the workspace") from None


class ListFiles(WorkspaceTool):
    name = "list_files"
    description = "List immediate entries in a workspace directory; directories end in /"

    def __init__(self, workspace: str | Path | None = None, *, max_entries: int = 1000) -> None:
        super().__init__(workspace)
        if type(max_entries) is not int or max_entries <= 0:
            raise ConfigurationError("ListFiles max_entries must be a positive integer")
        self.max_entries = max_entries

    def run(self, path: str = ".") -> list[str]:
        target = self.resolve_path(path)
        try:
            entries: list[str] = []
            for entry in target.iterdir():
                # Do not follow escaping symlinks just to classify an entry.
                if entry.is_symlink():
                    label = entry.name + "@"
                else:
                    label = entry.name + ("/" if entry.is_dir() else "")
                entries.append(label)
                if len(entries) > self.max_entries:
                    raise ToolError("Directory exceeds ListFiles max_entries")
            return sorted(entries)
        except OSError:
            raise ToolError("Cannot list workspace directory") from None
