"""Deterministic providers shared by offline tests and examples."""

from collections.abc import Sequence
from copy import deepcopy

from harness.models import Message, ModelResponse, ToolSchema
from harness.providers import BaseProvider


class FakeProvider(BaseProvider):
    def __init__(self, *responses: ModelResponse) -> None:
        self.responses = list(responses) or [ModelResponse(text="Hello")]
        self.requests: list[list[Message]] = []
        self.schemas: list[list[ToolSchema]] = []

    def generate(
        self, messages: Sequence[Message], tools: Sequence[ToolSchema] | None = None
    ) -> ModelResponse:
        self.requests.append(deepcopy(list(messages)))
        self.schemas.append(list(tools or []))
        return self.responses.pop(0)
