"""Bounded conversation context that preserves complete tool exchanges."""

from __future__ import annotations

import json
from collections.abc import Sequence
from copy import deepcopy
from dataclasses import asdict

from harness.exceptions import ConfigurationError, ContextLimitError
from harness.models import Message, ModelResponse


class Context:
    """Keep system prompt and newest complete turns; never split a tool exchange.

    max_chars is an approximate character budget, not a provider token counter.
    A current turn exceeding the budget raises ContextLimitError.
    """

    def __init__(
        self,
        system_prompt: str | None = None,
        *,
        max_messages: int = 100,
        max_chars: int = 100_000,
    ) -> None:
        if any(type(value) is not int or value <= 0 for value in (max_messages, max_chars)):
            raise ConfigurationError("Context limits must be positive integers")
        self.system_prompt = system_prompt
        self.max_messages = max_messages
        self.max_chars = max_chars
        self._messages: list[Message] = []
        self.clear()

    @property
    def messages(self) -> list[Message]:
        return deepcopy(self._messages)

    def _restore(self, messages: Sequence[Message]) -> None:
        self._messages = deepcopy(list(messages))

    def add_user(self, content: str) -> None:
        self._messages.append(Message("user", content))

    def add_assistant(self, response: ModelResponse) -> None:
        self._messages.append(
            Message(
                "assistant",
                response.text or "",
                deepcopy(response.tool_calls),
                provider_data=deepcopy(response.provider_data),
            )
        )

    def add_tool_result(self, call_id: str, result: str) -> None:
        self._messages.append(Message("tool", result, call_id=call_id))

    def clear(self) -> None:
        self._messages = [Message("system", self.system_prompt)] if self.system_prompt else []

    def trim(self) -> None:
        def over_budget() -> bool:
            size = len(json.dumps([asdict(message) for message in self._messages]))
            return len(self._messages) > self.max_messages or size > self.max_chars

        while over_budget():
            starts = [i for i, message in enumerate(self._messages) if message.role == "user"]
            if len(starts) < 2:
                raise ContextLimitError("The active conversation turn exceeds the context budget")
            del self._messages[starts[0] : starts[1]]
