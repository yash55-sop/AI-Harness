"""Offline command execution, timeout, output limits and workspace control."""

import sys
import time
from pathlib import Path

import pytest

from harness import Agent
from harness.exceptions import ConfigurationError, ToolError
from harness.tools import Shell, ShellTool


def test_stdout_stderr_exit_code_and_cwd(tmp_path: Path) -> None:
    result = Shell(tmp_path).execute(
        command=[
            sys.executable,
            "-c",
            "import os,sys; print(os.getcwd()); print('error',file=sys.stderr); sys.exit(3)",
        ]
    )
    assert str(tmp_path) in result["stdout"]
    assert result["stderr"].strip() == "error"
    assert result["exit_code"] == 3
    assert not result["timeout"]
    assert not result["truncated"]
    assert ShellTool is Shell


def test_string_command(tmp_path: Path) -> None:
    result = Shell(tmp_path).execute(command=f'"{sys.executable}" -c "print(123)"')
    assert result["stdout"].strip() == "123"


def test_no_implicit_shell(tmp_path: Path) -> None:
    marker = tmp_path / "must-not-exist"
    result = Shell(tmp_path).execute(
        command=[sys.executable, "-c", "import sys; print(sys.argv[1:])", ";", "touch", str(marker)]
    )
    assert result["exit_code"] == 0
    assert not marker.exists()


def test_timeout_retains_partial_output(tmp_path: Path) -> None:
    start = time.monotonic()
    result = Shell(tmp_path, timeout=2.0).execute(
        command=[sys.executable, "-c", "import time; print('started',flush=True); time.sleep(10)"]
    )
    assert result["timeout"]
    assert result["exit_code"] != 0
    assert "started" in result["stdout"]
    assert time.monotonic() - start < 8


def test_output_capture_is_bounded(tmp_path: Path) -> None:
    result = Shell(tmp_path, max_output_length=100).execute(
        command=[
            sys.executable,
            "-c",
            "import sys; sys.stdout.write('x'*100000); sys.stderr.write('y'*100000)",
        ]
    )
    assert len(result["stdout"]) + len(result["stderr"]) <= 100
    assert result["truncated"]
    assert result["exit_code"] == 0


@pytest.mark.parametrize(
    "command", [[], "", '"unbalanced', ["missing-executable-abcdef"], ["\x00"]]
)
def test_invalid_commands(tmp_path: Path, command: str | list[str]) -> None:
    with pytest.raises(ToolError):
        Shell(tmp_path).execute(command=command)


def test_binding(tmp_path: Path) -> None:
    original = Shell()
    agent = Agent("fake/model", workspace=tmp_path, tools=[original])
    bound = agent._registry.get("shell")
    assert bound.cwd == tmp_path.resolve()
    assert original.cwd != bound.cwd


@pytest.mark.parametrize(
    "kwargs", [{"timeout": 0}, {"timeout": float("nan")}, {"max_output_length": 0}]
)
def test_invalid_options(tmp_path: Path, kwargs: dict[str, float]) -> None:
    with pytest.raises(ConfigurationError):
        Shell(tmp_path, **kwargs)


def test_invalid_cwd(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        Shell(tmp_path / "missing")
