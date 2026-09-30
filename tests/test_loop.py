"""Agent execution, errors, transactional history, metadata, and safe logs."""

import json
import logging
from typing import Any

import pytest

from harness import Agent
from harness.exceptions import (
    ConfigurationError,
    ContextLimitError,
    MaxStepsExceeded,
    ProviderError,
    ToolError,
    ToolNotFoundError,
    ToolValidationError,
)
from harness.models import ModelResponse, ToolCall, Usage
from harness.tools import Tool
from tests.fakes import FakeProvider
from tests.test_tools import Add


def test_calculator_loop_and_metadata() -> None:
    call = ToolCall("c1", "add", {"a": 2, "b": 3})
    provider = FakeProvider(
        ModelResponse(tool_calls=[call], usage=Usage(10, 4)),
        ModelResponse(text="5", usage=Usage(15, 1)),
    )
    agent = Agent("fake/model", provider=provider, tools=[Add()])
    assert agent.run("Add 2 and 3") == "5"
    assert provider.requests[1][-1].content == "5"
    assert provider.requests[1][-1].call_id == "c1"
    assert provider.requests[1][-2].tool_calls == [call]
    assert provider.schemas[0][0].name == "add"
    assert agent.last_result is not None
    assert agent.last_result.steps == 2
    assert agent.last_result.usage == Usage(25, 5)
    assert agent.last_result.tool_calls == [call]
    assert str(agent.last_result) == "5"
    assert agent.last_result.duration >= 0


@pytest.mark.parametrize(
    "call,error",
    [
        (ToolCall("c1", "missing", {}), ToolNotFoundError),
        (ToolCall("c1", "add", {"a": "secret"}), ToolValidationError),
    ],
)
def test_invalid_calls_restore_context(call: ToolCall, error: type[Exception]) -> None:
    provider = FakeProvider(ModelResponse(tool_calls=[call]), ModelResponse(text="recovered"))
    agent = Agent("fake/model", provider=provider, tools=[Add()], system_prompt="system")
    checkpoint = agent.history
    with pytest.raises(error):
        agent.run("bad")
    assert agent.history == checkpoint
    assert agent.last_result is None
    assert agent.run("retry") == "recovered"


def test_entire_batch_is_validated_before_execution() -> None:
    executions = []

    class SideEffect(Add):
        def run(self, a: int, b: int = 1) -> int:
            executions.append(a)
            return a + b

    provider = FakeProvider(
        ModelResponse(
            tool_calls=[ToolCall("c1", "add", {"a": 1}), ToolCall("c2", "add", {"a": "invalid"})]
        )
    )
    with pytest.raises(ToolValidationError):
        Agent("fake/model", provider=provider, tools=[SideEffect()]).run("bad")
    assert not executions


def test_step_limit() -> None:
    provider = FakeProvider(
        *[ModelResponse(tool_calls=[ToolCall(f"c{i}", "add", {"a": i})]) for i in range(3)]
    )
    agent = Agent("fake/model", provider=provider, tools=[Add()], max_steps=3)
    with pytest.raises(MaxStepsExceeded):
        agent.run("loop")
    assert len(provider.requests) == 3
    assert agent.history == []


def test_provider_failures_are_wrapped() -> None:
    class Broken(FakeProvider):
        def generate(self, *args: Any, **kwargs: Any) -> ModelResponse:
            raise RuntimeError("private-secret")

    with pytest.raises(ProviderError) as caught:
        Agent("fake/model", provider=Broken()).run("hello")
    assert "private-secret" not in str(caught.value)


def test_duplicate_call_ids() -> None:
    call = ToolCall("c1", "add", {"a": 1})
    with pytest.raises(ProviderError, match="duplicate"):
        Agent(
            "fake/model",
            provider=FakeProvider(ModelResponse(tool_calls=[call, call])),
            tools=[Add()],
        ).run("hello")


def test_history_and_reset() -> None:
    provider = FakeProvider(ModelResponse(text="first"), ModelResponse(text="second"))
    agent = Agent("fake/model", provider=provider)
    agent.run("one")
    agent.run("two")
    assert [message.content for message in provider.requests[-1]] == ["one", "first", "two"]
    agent.reset()
    assert agent.history == []
    assert agent.last_result is None
    agent.add_tool(Add())


def test_context_limit_restores_prior_state() -> None:
    agent = Agent("fake/model", provider=FakeProvider(), max_context_chars=100)
    with pytest.raises(ContextLimitError):
        agent.run("x" * 200)
    assert not agent.history


def test_tool_output_is_bounded_and_non_serializable_rejected() -> None:
    class Output(Tool):
        name = "output"
        description = "Return text"

        def run(self) -> str:
            return "x" * 200

    provider = FakeProvider(
        ModelResponse(tool_calls=[ToolCall("c1", "output", {})]), ModelResponse(text="done")
    )
    agent = Agent("fake/model", provider=provider, tools=[Output()], max_tool_output=40)
    agent.run("go")
    assert len(provider.requests[-1][-1].content) == 40
    assert provider.requests[-1][-1].content.endswith("[output truncated]")

    class BadOutput(Output):
        def run(self) -> Any:
            return object()

    with pytest.raises(ToolError, match="serializable"):
        Agent(
            "fake/model",
            provider=FakeProvider(ModelResponse(tool_calls=[ToolCall("c1", "output", {})])),
            tools=[BadOutput()],
        ).run("go")


def test_verbose_logs_do_not_include_secrets(capsys: pytest.CaptureFixture[str]) -> None:
    Agent("fake/model", provider=FakeProvider(), api_key="key-secret", verbose=True).run(
        "prompt-secret"
    )
    captured = capsys.readouterr()
    assert not captured.out
    assert "key-secret" not in captured.err
    assert "prompt-secret" not in captured.err
    events = [json.loads(line)["event"] for line in captured.err.splitlines()]
    assert events == ["step_start", "finished"]


def test_standard_logger_and_no_global_configuration(caplog: pytest.LogCaptureFixture) -> None:
    handlers = list(logging.getLogger().handlers)
    with caplog.at_level(logging.INFO, logger="harness.agent"):
        Agent("fake/model", provider=FakeProvider()).run("hello")
    assert "finished" in caplog.text
    assert logging.getLogger().handlers == handlers


def test_recursive_run_reset_and_tool_changes_rejected() -> None:
    agent = Agent("fake/model", provider=FakeProvider())
    agent._running = True
    for operation in (
        lambda: agent.run("hi"),
        agent.reset,
        agent.close,
        lambda: agent.add_tool(Add()),
    ):
        with pytest.raises(ConfigurationError):
            operation()


def test_injected_provider_is_not_closed() -> None:
    closed = []

    class Owned(FakeProvider):
        def close(self) -> None:
            closed.append(True)

    with Agent("fake/model", provider=Owned()) as agent:
        agent.run("hi")
    assert not closed


def test_invalid_output_limit() -> None:
    with pytest.raises(ConfigurationError):
        Agent("fake/model", max_tool_output=0)


def test_invalid_provider_response_is_a_clear_error() -> None:
    provider = FakeProvider(ModelResponse(text=42))  # type: ignore[arg-type]
    with pytest.raises(ProviderError, match="normalized"):
        Agent("fake/model", provider=provider).run("hi")


def test_owned_provider_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    closed = []

    class Owned(FakeProvider):
        def close(self) -> None:
            closed.append(True)

    monkeypatch.setattr("harness.agent.get_provider", lambda *args, **kwargs: Owned())
    with Agent("fake/model") as agent:
        assert agent.run("hi") == "Hello"
    assert closed == [True]
