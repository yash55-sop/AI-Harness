"""Provider-neutral conversation and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ToolCall:
    """A request to execute a named tool with JSON arguments."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens, self.output_tokens + other.output_tokens
        )


@dataclass(frozen=True)
class ToolSchema:
    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ModelResponse:
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage | None = None
    finish_reason: str | None = None
    # Opaque provider-owned continuation data. The runtime only stores it.
    provider_data: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


@dataclass(frozen=True)
class Message:
    role: Literal["system", "user", "assistant", "tool"]
    content: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    call_id: str | None = None
    provider_data: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class RunResult:
    """Metadata for the last successful run. Agent.run still returns a string."""

    output: str
    steps: int
    usage: Usage
    duration: float
    tool_calls: list[ToolCall] = field(default_factory=list)

    def __str__(self) -> str:
        return self.output
