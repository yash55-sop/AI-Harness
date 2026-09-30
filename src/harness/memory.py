"""Simple application memory, separate from model conversation context."""

from abc import ABC, abstractmethod
from typing import Any


class Memory(ABC):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        """Return a value or default."""

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Store a value."""

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove a value if present."""


class InMemoryMemory(Memory):
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._values[key] = value

    def delete(self, key: str) -> None:
        self._values.pop(key, None)
