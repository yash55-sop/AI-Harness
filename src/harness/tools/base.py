"""Typed tools and a per-agent registry."""

from __future__ import annotations

import inspect
import re
from abc import ABC, abstractmethod
from collections.abc import Sequence
from functools import cached_property
from typing import Any, get_type_hints

from pydantic import BaseModel, ConfigDict, ValidationError, create_model

from harness.exceptions import (
    ConfigurationError,
    DuplicateToolError,
    ToolError,
    ToolNotFoundError,
    ToolValidationError,
)
from harness.models import ToolSchema


class Tool(ABC):
    """Subclass with a typed run method, optionally declaring input_model."""

    name: str
    description: str
    input_model: type[BaseModel] | None = None

    @abstractmethod
    def run(self, *args: Any, **kwargs: Any) -> Any:
        """Perform the operation; use execute() to validate inputs first."""

    @cached_property
    def _inputs(self) -> type[BaseModel]:
        if self.input_model is not None:
            return self.input_model
        fields: dict[str, Any] = {}
        try:
            hints = get_type_hints(self.run)
            for name, parameter in inspect.signature(self.run).parameters.items():
                if parameter.kind not in (
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    inspect.Parameter.KEYWORD_ONLY,
                ):
                    raise ConfigurationError("Tool run parameters must be named inputs")
                if name not in hints:
                    raise ConfigurationError("Every tool input needs a type annotation")
                default = ... if parameter.default is inspect.Parameter.empty else parameter.default
                fields[name] = (hints[name], default)
            return create_model(
                f"{type(self).__name__}Input",
                __config__=ConfigDict(extra="forbid", strict=True),
                **fields,
            )
        except ConfigurationError:
            raise
        except (NameError, TypeError, ValueError):
            raise ConfigurationError(
                "Cannot derive tool input schema; declare input_model"
            ) from None

    @property
    def schema(self) -> ToolSchema:
        if not hasattr(self, "name") or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", self.name):
            raise ConfigurationError(
                "Tool names must be 1–64 letters, digits, underscores or hyphens"
            )
        if not getattr(self, "description", "").strip():
            raise ConfigurationError("Tools need a nonempty description")
        parameters = self._inputs.model_json_schema()
        parameters["additionalProperties"] = False
        return ToolSchema(self.name, self.description, parameters)

    def validate(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Validate JSON-shaped arguments without echoing input or credentials."""
        allowed = self.schema.parameters.get("properties", {})
        if not isinstance(arguments, dict) or set(arguments) - set(allowed):
            raise ToolValidationError("Tool arguments contain unknown fields or are not an object")
        try:
            validated = self._inputs.model_validate(arguments, strict=True)
        except ValidationError as error:
            fields = ", ".join(
                ".".join(str(part) for part in item["loc"])
                for item in error.errors(include_input=False, include_url=False)
            )
            raise ToolValidationError(f"Invalid tool inputs: {fields}") from None
        return validated.model_dump()

    def execute(self, **arguments: Any) -> Any:
        """Validate inputs and translate implementation failures to ToolError."""
        validated = self.validate(arguments)
        try:
            return self.run(**validated)
        except ToolError:
            raise
        except Exception:
            raise ToolError(f"Tool {self.name!r} failed") from None


class ToolRegistry:
    """Named tools owned by one agent; duplicate registration is an error."""

    def __init__(self, tools: Sequence[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.add(tool)

    def add(self, tool: Tool) -> None:
        if not isinstance(tool, Tool):
            raise ConfigurationError("tools must contain Tool instances")
        schema = tool.schema
        if schema.name in self._tools:
            raise DuplicateToolError(f"Tool {schema.name!r} is already registered")
        self._tools[schema.name] = tool

    def get(self, name: str) -> Tool:
        try:
            return self._tools[name]
        except KeyError:
            raise ToolNotFoundError("The model requested an unregistered tool") from None

    @property
    def schemas(self) -> list[ToolSchema]:
        return [tool.schema for tool in self._tools.values()]
