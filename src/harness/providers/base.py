"""The synchronous contract implemented by model providers."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from harness.models import Message, ModelResponse, ToolSchema


class BaseProvider(ABC):
    @abstractmethod
    def generate(
        self, messages: Sequence[Message], tools: Sequence[ToolSchema] | None = None
    ) -> ModelResponse:
        """Generate a normalized answer or tool requests."""

    def close(self) -> None:
        """Release owned resources, if any."""
        return None
