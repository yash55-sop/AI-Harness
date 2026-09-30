"""Convenience Agent configuration for working on a repository."""

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from harness.agent import Agent
from harness.tools import ListFiles, ReadFile, Shell, Tool, WriteFile

CODING_PROMPT = (
    "You are a coding assistant working in the configured workspace. "
    "Inspect relevant files before changing them. Make focused edits, verify changes "
    "with appropriate tests, and explain the result. Shell commands have the user's "
    "process permissions; avoid destructive commands and reading credentials."
)


class CodingAgent(Agent):
    """Reuse Agent with workspace filesystem tools and optional shell execution."""

    def __init__(
        self,
        model: str,
        workspace: str | Path = ".",
        api_key: str | None = None,
        *,
        tools: Sequence[Tool] | None = None,
        enable_shell: bool = True,
        shell_timeout: float = 30.0,
        max_shell_output: int = 20_000,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> None:
        builtins: list[Tool] = [ReadFile(workspace), WriteFile(workspace), ListFiles(workspace)]
        if enable_shell:
            builtins.append(
                Shell(workspace, timeout=shell_timeout, max_output_length=max_shell_output)
            )
        super().__init__(
            model=model,
            api_key=api_key,
            workspace=workspace,
            tools=[*builtins, *(tools or [])],
            system_prompt=system_prompt if system_prompt is not None else CODING_PROMPT,
            **kwargs,
        )
