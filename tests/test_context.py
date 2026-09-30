"""Context budgets preserve systems and entire user/tool turns."""

import pytest

from harness import Context
from harness.exceptions import ConfigurationError, ContextLimitError
from harness.models import ModelResponse, ToolCall


def test_normalized_messages_and_clear() -> None:
    context = Context("Be helpful")
    context.add_user("hi")
    context.add_assistant(ModelResponse(tool_calls=[ToolCall("c1", "add", {"a": 1})]))
    context.add_tool_result("c1", "2")
    assert [message.role for message in context.messages] == ["system", "user", "assistant", "tool"]
    context.clear()
    assert len(context.messages) == 1
    assert context.messages[0].content == "Be helpful"


def test_snapshot_is_defensive() -> None:
    context = Context()
    context.add_assistant(ModelResponse(tool_calls=[ToolCall("c1", "x", {"key": 1})]))
    snapshot = context.messages
    snapshot[0].tool_calls[0].arguments["key"] = 999
    snapshot.clear()
    assert context.messages[0].tool_calls[0].arguments["key"] == 1


def test_trim_complete_turns() -> None:
    context = Context("system", max_messages=4)
    context.add_user("old")
    context.add_assistant(ModelResponse(tool_calls=[ToolCall("c1", "x", {})]))
    context.add_tool_result("c1", "old-result")
    context.add_assistant(ModelResponse(text="old-answer"))
    context.add_user("new")
    context.add_assistant(ModelResponse(text="new-answer"))
    context.trim()
    assert [message.content for message in context.messages] == ["system", "new", "new-answer"]


def test_oversized_current_turn() -> None:
    context = Context(max_messages=1)
    context.add_user("hi")
    context.add_assistant(ModelResponse(text="hello"))
    with pytest.raises(ContextLimitError):
        context.trim()
    chars = Context(max_chars=10)
    chars.add_user("x" * 20)
    with pytest.raises(ContextLimitError):
        chars.trim()


@pytest.mark.parametrize("kwargs", [{"max_chars": 0}, {"max_messages": -1}, {"max_chars": True}])
def test_invalid_budgets(kwargs: dict[str, int]) -> None:
    with pytest.raises(ConfigurationError):
        Context(**kwargs)
