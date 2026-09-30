"""Verify Windows directory-junction escapes without requiring symlink privileges."""

import subprocess
import sys
from pathlib import Path

import pytest

from harness.exceptions import ToolError
from harness.tools import ListFiles, ReadFile, WriteFile


@pytest.mark.skipif(sys.platform != "win32", reason="Windows directory junction")
def test_junction_cannot_escape_workspace(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    outside = tmp_path / "outside"
    workspace.mkdir()
    outside.mkdir()
    (outside / "secret.txt").write_text("original", encoding="utf-8")
    junction = workspace / "linked"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(outside)], check=True, capture_output=True
    )
    with pytest.raises(ToolError):
        ReadFile(workspace).execute(path="linked/secret.txt")
    with pytest.raises(ToolError):
        WriteFile(workspace).execute(path="linked/new.txt", content="escape")
    with pytest.raises(ToolError):
        ListFiles(workspace).execute(path="linked")
    assert not (outside / "new.txt").exists()
