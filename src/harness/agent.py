"""A bounded synchronous agent runtime with replaceable providers and tools."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from harness.config import AgentConfig
from harness.context import Context
from harness.exceptions import (
    ConfigurationError,
    HarnessError,
    MaxStepsExceeded,
    ProviderError,
    ToolError,
)
from harness.logging import agent_logger
from harness.memory import InMemoryMemory, Memory
from harness.models import Message, ModelResponse, RunResult, ToolCall, Usage
from harness.providers import BaseProvider, get_provider
from harness.tools.base import Tool, ToolRegistry
from harness.tools.filesystem import WorkspaceTool
from harness.tools.shell import Shell


class Agent:
    """Run model → tools → observations until the model returns an answer.

    Synchronous and not thread-safe. run() preserves conversation history;
    reset() starts a new conversation. Plain Agent has no default tools.
    Providers are created lazily so construction never requires credentials.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        system_prompt: str | None = None,
        max_steps: int | None = None,
        verbose: bool = False,
        *,
        temperature: float | None = 0.2,
        tools: Sequence[Tool] | None = None,
        provider: BaseProvider | None = None,
        workspace: str | Path | None = None,
        max_context_messages: int = 100,
        max_context_chars: int = 100_000,
        max_tool_output: int = 20_000,
        memory: Memory | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.config = AgentConfig.from_env(
            model=model,
            api_key=api_key,
            system_prompt=system_prompt,
            max_steps=max_steps,
            verbose=verbose,
            temperature=temperature,
        )
        self._temperature = self.config.temperature
        if type(max_tool_output) is not int or max_tool_output <= 0:
            raise ConfigurationError("max_tool_output must be a positive integer")
        self.max_tool_output = max_tool_output
        self.workspace = Path(workspace).resolve() if workspace is not None else None
        if self.workspace is not None and not self.workspace.is_dir():
            raise ConfigurationError("Workspace must be an existing directory")
        self.context = Context(
            system_prompt, max_messages=max_context_messages, max_chars=max_context_chars
        )
        self.memory = memory if memory is not None else InMemoryMemory()
        self._registry = ToolRegistry()
        for tool in tools or []:
            self._registry.add(self._bind_tool(tool))
        self._provider = provider
        self._owns_provider = provider is None
        self._logger = (
            logger if logger is not None else agent_logger(verbose, self.config.log_level)
        )
        self.last_result: RunResult | None = None
        self._running = False

    @property
    def provider(self) -> BaseProvider:
        if self._provider is None:
            key = self.config.api_key
            self._provider = get_provider(
                self.config.model,
                api_key=key.get_secret_value() if key is not None else None,
                temperature=self._temperature,
            )
        return self._provider

    @property
    def history(self) -> list[Message]:
        return self.context.messages

    def add_tool(self, tool: Tool) -> None:
        """Register a tool; duplicate names are rejected."""
        if self._running:
            raise ConfigurationError("Cannot change tools during a run")
        self._registry.add(self._bind_tool(tool))

    def _bind_tool(self, tool: Tool) -> Tool:
        if self.workspace is not None and isinstance(tool, (WorkspaceTool, Shell)):
            return tool.bind_workspace(self.workspace)
        return tool

    def reset(self) -> None:
        """Clear history and last result, preserving tools and memory."""
        if self._running:
            raise ConfigurationError("Cannot reset an active run")
        self.context.clear()
        self.last_result = None

    def _serialize_result(self, result: Any) -> str:
        try:
            output = result if isinstance(result, str) else json.dumps(result, allow_nan=False)
        except (TypeError, ValueError):
            raise ToolError("Tool returned a result that is not JSON serializable") from None
        if len(output) > self.max_tool_output:
            marker = "\n[output truncated]"
            output = output[: max(0, self.max_tool_output - len(marker))]
            output += marker[: self.max_tool_output - len(output)]
        return output

    def run(self, task: str) -> str:
        """Return an answer and expose successful run metadata in last_result.

        Failures restore the prior conversation to avoid incomplete tool exchanges.
        Already executed tool side effects cannot be rolled back.
        """
        if not isinstance(task, str) or not task.strip():
            raise ConfigurationError("task must be a nonempty string")
        if self._running:
            raise ConfigurationError("An agent cannot run recursively or concurrently")
        checkpoint = self.context.messages
        self._running = True
        self.last_result = None
        start = time.monotonic()
        usage = Usage()
        calls: list[ToolCall] = []
        try:
            self.context.add_user(task)
            for step in range(1, self.config.max_steps + 1):
                self.context.trim()
                self._logger.info("step_start", extra={"step": step})
                try:
                    response = self.provider.generate(self.context.messages, self._registry.schemas)
                except HarnessError:
                    raise
                except Exception:
                    raise ProviderError("The provider failed to generate a response") from None
                if not isinstance(response, ModelResponse) or (
                    response.text is not None and not isinstance(response.text, str)
                ):
                    raise ProviderError("The provider must return a normalized ModelResponse")
                usage += response.usage or Usage()
                self.context.add_assistant(response)
                if response.tool_calls:
                    ids = [call.id for call in response.tool_calls]
                    if len(ids) != len(set(ids)) or any(not name for name in ids):
                        raise ProviderError(
                            "The provider returned duplicate or empty tool call IDs"
                        )
                    # Validate the whole batch before any tool side effects occur.
                    for call in response.tool_calls:
                        self._registry.get(call.name).validate(call.arguments)
                    for call in response.tool_calls:
                        self._logger.info("tool_start", extra={"step": step, "tool": call.name})
                        tool = self._registry.get(call.name)
                        output = self._serialize_result(tool.execute(**call.arguments))
                        self.context.add_tool_result(call.id, output)
                        calls.append(call)
                        self._logger.info("tool_end", extra={"step": step, "tool": call.name})
                    continue
                if response.text is None:
                    raise ProviderError("The model returned no text or tool calls")
                self.context.trim()
                self.last_result = RunResult(
                    response.text, step, usage, time.monotonic() - start, calls
                )
                self._logger.info(
                    "finished", extra={"step": step, "duration": self.last_result.duration}
                )
                return response.text
            raise MaxStepsExceeded(f"The agent exceeded {self.config.max_steps} model steps")
        except BaseException as error:
            self.context._restore(checkpoint)
            self._logger.error("run_failed", extra={"error_type": type(error).__name__})
            raise
        finally:
            self._running = False

    def close(self) -> None:
        """Close an owned provider; injected providers remain caller-owned."""
        if self._running:
            raise ConfigurationError("Cannot close an active run")
        if self._owns_provider and self._provider is not None:
            self._provider.close()
            self._provider = None

    def __enter__(self) -> Agent:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
