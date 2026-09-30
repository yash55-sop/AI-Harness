"""Explicit command execution with bounded capture and a timeout."""

from __future__ import annotations

import math
import os
import shlex
import signal
import subprocess
import sys
import threading
import time
from copy import copy
from pathlib import Path
from typing import BinaryIO, TypedDict

from harness.exceptions import ConfigurationError, ToolError
from harness.tools.base import Tool


class ShellResult(TypedDict):
    stdout: str
    stderr: str
    exit_code: int
    timeout: bool
    truncated: bool


class Shell(Tool):
    """Run an executable without shell=True. This is not an OS sandbox.

    Prefer a list of arguments, especially for paths with spaces on Windows.
    Shell operators require an explicit interpreter invocation. Commands inherit
    the process environment and have the same permissions as the Python process.
    """

    name = "shell"
    description = "Execute a command in the workspace; prefer a list of executable arguments"

    def __init__(
        self,
        cwd: str | Path | None = None,
        *,
        timeout: float = 30.0,
        max_output_length: int = 20_000,
    ) -> None:
        self.cwd = Path(cwd if cwd is not None else Path.cwd()).resolve()
        if not self.cwd.is_dir():
            raise ConfigurationError("Shell cwd must be an existing directory")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ConfigurationError("Shell timeout must be finite and positive")
        if type(max_output_length) is not int or max_output_length <= 0:
            raise ConfigurationError("Shell max_output_length must be a positive integer")
        self.timeout = timeout
        self.max_output_length = max_output_length

    def bind_workspace(self, workspace: Path) -> Shell:
        if not workspace.is_dir():
            raise ConfigurationError("Workspace must be an existing directory")
        bound = copy(self)
        bound.cwd = workspace.resolve()
        return bound

    @staticmethod
    def _terminate(process: subprocess.Popen[bytes]) -> None:
        if sys.platform == "win32":
            try:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    timeout=5,
                    check=False,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
            except (OSError, subprocess.TimeoutExpired):
                pass  # Fall back to killing the direct child below.
        else:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.kill()

    def run(self, command: str | list[str]) -> ShellResult:
        if isinstance(command, str):
            try:
                arguments = shlex.split(command, posix=sys.platform != "win32")
            except ValueError:
                raise ToolError("Command contains unbalanced quotes") from None
            if sys.platform == "win32":
                arguments = [
                    item[1:-1]
                    if len(item) >= 2 and item[0] == item[-1] and item[0] in ('"', "'")
                    else item
                    for item in arguments
                ]
        else:
            arguments = list(command)
        if not arguments or not arguments[0] or any("\x00" in item for item in arguments):
            raise ToolError("Command must contain an executable and valid arguments")
        buffers = [bytearray(), bytearray()]
        total = 0
        truncated = False
        lock = threading.Lock()

        def capture(stream: BinaryIO, index: int) -> None:
            nonlocal total, truncated
            try:
                while chunk := stream.read(4096):
                    with lock:
                        remaining = self.max_output_length - total
                        buffers[index].extend(chunk[:remaining])
                        total += min(len(chunk), remaining)
                        truncated |= len(chunk) > remaining
            finally:
                stream.close()

        creation_flags = 0
        if sys.platform == "win32":
            creation_flags = subprocess.CREATE_NO_WINDOW
        try:
            process = subprocess.Popen(
                arguments,
                cwd=self.cwd,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=sys.platform != "win32",
                creationflags=creation_flags,
            )
        except (OSError, ValueError):
            raise ToolError("Cannot start the requested executable") from None
        assert process.stdout is not None and process.stderr is not None
        threads = [
            threading.Thread(target=capture, args=(stream, index), daemon=True)
            for index, stream in enumerate((process.stdout, process.stderr))
        ]
        for thread in threads:
            thread.start()
        timed_out = False
        try:
            process.wait(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            self._terminate(process)
            process.wait(timeout=5)
        except BaseException:
            self._terminate(process)
            process.wait(timeout=5)
            raise
        deadline = time.monotonic() + 1.0
        for thread in threads:
            thread.join(timeout=max(0, deadline - time.monotonic()))
        with lock:
            return {
                "stdout": bytes(buffers[0]).decode("utf-8", errors="replace"),
                "stderr": bytes(buffers[1]).decode("utf-8", errors="replace"),
                "exit_code": process.returncode,
                "timeout": timed_out,
                "truncated": truncated or any(thread.is_alive() for thread in threads),
            }


ShellTool = Shell
