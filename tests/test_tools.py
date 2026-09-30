"""Tool schema, validation, execution and registry behavior."""

from typing import Any

import pytest
from pydantic import BaseModel, Field

from harness.exceptions import (
    ConfigurationError,
    DuplicateToolError,
    ToolError,
    ToolNotFoundError,
    ToolValidationError,
)
from harness.tools import Tool, ToolRegistry


class Add(Tool):
    name = "add"
    description = "Add two integers"

    def run(self, a: int, b: int = 1) -> int:
        return a + b


def test_signature_schema_and_execution() -> None:
    tool = Add()
    assert tool.schema.parameters["properties"]["a"]["type"] == "integer"
    assert tool.schema.parameters["required"] == ["a"]
    assert tool.execute(a=2, b=3) == 5
    assert tool.execute(a=2) == 3


@pytest.mark.parametrize("arguments", [{}, {"a": "2"}, {"a": True}, {"a": 2, "extra": 3}])
def test_validation_prevents_execution(arguments: dict[str, Any]) -> None:
    with pytest.raises(ToolValidationError):
        Add().execute(**arguments)


def test_explicit_pydantic_inputs() -> None:
    class Inputs(BaseModel):
        value: int = Field(gt=0)

    class Positive(Tool):
        name = "positive"
        description = "Return a positive value"
        input_model = Inputs

        def run(self, **kwargs: Any) -> int:
            return int(kwargs["value"])

    assert Positive().execute(value=2) == 2
    with pytest.raises(ToolValidationError):
        Positive().execute(value=-1)
    with pytest.raises(ToolValidationError):
        Positive().execute(value=1, extra=True)


def test_tool_failures_are_translated_and_redacted() -> None:
    class Fails(Add):
        def run(self, a: int, b: int = 1) -> int:
            raise RuntimeError("private-secret")

    with pytest.raises(ToolError) as caught:
        Fails().execute(a=1)
    assert "private-secret" not in str(caught.value)


def test_tool_error_is_preserved() -> None:
    class Fails(Add):
        def run(self, a: int, b: int = 1) -> int:
            raise ToolError("operation denied")

    with pytest.raises(ToolError, match="denied"):
        Fails().execute(a=1)


def test_registry() -> None:
    tool = Add()
    registry = ToolRegistry([tool])
    assert registry.get("add") is tool
    assert registry.schemas == [tool.schema]
    with pytest.raises(DuplicateToolError):
        registry.add(Add())
    with pytest.raises(ToolNotFoundError):
        registry.get("missing")
    with pytest.raises(ConfigurationError):
        registry.add(object())  # type: ignore[arg-type]


def test_registry_is_per_instance() -> None:
    first = ToolRegistry([Add()])
    second = ToolRegistry()
    assert len(first.schemas) == 1
    assert not second.schemas


@pytest.mark.parametrize("name,description", [("bad name", "valid"), ("x", ""), ("", "valid")])
def test_invalid_tool_metadata(name: str, description: str) -> None:
    tool = Add()
    tool.name = name
    tool.description = description
    with pytest.raises(ConfigurationError):
        ToolRegistry([tool])


def test_missing_annotation() -> None:
    class Untyped(Add):
        def run(self, a, b=1):  # type: ignore[no-untyped-def]
            return a + b

    with pytest.raises(ConfigurationError, match="annotation"):
        ToolRegistry([Untyped()])


def test_variadic_signature_needs_input_model() -> None:
    class Variadic(Add):
        def run(self, **kwargs: Any) -> int:
            return 1

    with pytest.raises(ConfigurationError, match="named"):
        ToolRegistry([Variadic()])
