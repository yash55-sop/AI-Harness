"""A minimal public interface for the AI agent harness."""

from harness.agent import Agent
from harness.coding import CodingAgent
from harness.config import AgentConfig
from harness.context import Context
from harness.exceptions import ConfigurationError, HarnessError
from harness.memory import InMemoryMemory, Memory
from harness.models import RunResult

__version__ = "0.1.0"
__all__ = [
    "Agent",
    "AgentConfig",
    "CodingAgent",
    "ConfigurationError",
    "Context",
    "HarnessError",
    "InMemoryMemory",
    "Memory",
    "RunResult",
    "__version__",
]
