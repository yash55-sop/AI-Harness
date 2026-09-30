"""Filesystem boundaries, UTF-8 handling, limits and tool binding."""

import os
from pathlib import Path

import pytest

from harness import Agent
from harness.exceptions import ConfigurationError, ToolError
from harness.tools import ListFiles, ReadFile, WriteFile


def test_write_read_list(tmp_path: Path) -> None:
    result = WriteFile(tmp_path).execute(path="src/main.py", content="print('héllo')\n")
    assert result["bytes_written"] == len("print('héllo')\n".encode())
    assert ReadFile(tmp_path).execute(path="src/main.py") == "print('héllo')\n"
    assert ListFiles(tmp_path).execute() == ["src/"]
    assert ListFiles(tmp_path).execute(path="src") == ["main.py"]
    WriteFile(tmp_path).execute(path="src/main.py", content="replacement")
    assert ReadFile(tmp_path).execute(path="src/main.py") == "replacement"


@pytest.mark.parametrize("tool_class", [ReadFile, WriteFile, ListFiles])
@pytest.mark.parametrize("path", ["../outside.txt", "sub/../../outside.txt"])
def test_rejects_traversal(tmp_path: Path, tool_class: type, path: str) -> None:
    tool = tool_class(tmp_path)
    arguments = {"path": path}
    if tool_class is WriteFile:
        arguments["content"] = "escape"
    with pytest.raises(ToolError, match="inside"):
        tool.execute(**arguments)


def test_absolute_paths(tmp_path: Path) -> None:
    target = tmp_path / "inside.txt"
    target.write_text("inside", encoding="utf-8")
    assert ReadFile(tmp_path).execute(path=str(target)) == "inside"
    with pytest.raises(ToolError):
        ReadFile(tmp_path).execute(path=str(tmp_path.parent / "outside.txt"))


def test_symlink_escape_for_read_write_and_directory(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("secret", encoding="utf-8")
    link = workspace / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation is not permitted on this platform")
    assert ListFiles(workspace).execute() == ["link@"]
    with pytest.raises(ToolError):
        ReadFile(workspace).execute(path="link/secret.txt")
    with pytest.raises(ToolError):
        WriteFile(workspace).execute(path="link/new.txt", content="escape")
    with pytest.raises(ToolError):
        ListFiles(workspace).execute(path="link")
    assert not (outside / "new.txt").exists()


def test_hardlink_overwrite_rejected(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    source = tmp_path / "outside.txt"
    source.write_text("original", encoding="utf-8")
    os.link(source, workspace / "link.txt")
    with pytest.raises(ToolError, match="hard-linked"):
        WriteFile(workspace).execute(path="link.txt", content="replacement")
    assert source.read_text() == "original"


def test_missing_directory_binary_and_large_files(tmp_path: Path) -> None:
    with pytest.raises(ToolError):
        ReadFile(tmp_path).execute(path="missing")
    with pytest.raises(ToolError, match="regular"):
        ReadFile(tmp_path).execute(path=".")
    (tmp_path / "binary").write_bytes(b"\xff")
    with pytest.raises(ToolError, match="UTF-8"):
        ReadFile(tmp_path).execute(path="binary")
    (tmp_path / "large").write_bytes(b"abc")
    with pytest.raises(ToolError, match="max_bytes"):
        ReadFile(tmp_path, max_bytes=2).execute(path="large")
    with pytest.raises(ToolError):
        WriteFile(tmp_path).execute(path=".", content="bad")
    with pytest.raises(ToolError):
        ListFiles(tmp_path).execute(path="missing")
    with pytest.raises(ToolError, match="max_entries"):
        ListFiles(tmp_path, max_entries=1).execute()


def test_workspace_binding_does_not_mutate_shared_tools(tmp_path: Path) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    shared = ReadFile(first)
    agent = Agent("fake/model", workspace=second, tools=[shared])
    bound = agent._registry.get("read_file")
    assert bound.workspace == second.resolve()
    assert shared.workspace == first.resolve()
    agent.add_tool(WriteFile(first))
    agent._registry.get("write_file").execute(path="file.txt", content="here")
    assert (second / "file.txt").is_file()
    assert not (first / "file.txt").exists()


@pytest.mark.parametrize(
    "tool_class,kwargs",
    [
        (ReadFile, {"max_bytes": 0}),
        (ListFiles, {"max_entries": 0}),
    ],
)
def test_invalid_limits(tmp_path: Path, tool_class: type, kwargs: dict[str, int]) -> None:
    with pytest.raises(ConfigurationError):
        tool_class(tmp_path, **kwargs)


def test_invalid_workspace(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        ReadFile(tmp_path / "missing")
    with pytest.raises(ConfigurationError):
        Agent("fake/model", workspace=tmp_path / "missing")


@pytest.mark.skipif(os.name != "nt", reason="NTFS-specific")
def test_alternate_data_stream_rejected(tmp_path: Path) -> None:
    with pytest.raises(ToolError):
        WriteFile(tmp_path).execute(path="file.txt:stream", content="bad")
