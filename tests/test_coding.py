"""A coding agent inspects a repository and changes a file via the shared loop."""

from pathlib import Path

from harness import CodingAgent
from harness.models import ModelResponse, ToolCall
from tests.fakes import FakeProvider


def test_coding_agent_inspects_and_modifies_repository(tmp_path: Path) -> None:
    target = tmp_path / "main.py"
    target.write_text("answer = 41\n", encoding="utf-8")
    provider = FakeProvider(
        ModelResponse(tool_calls=[ToolCall("list", "list_files", {})]),
        ModelResponse(tool_calls=[ToolCall("read", "read_file", {"path": "main.py"})]),
        ModelResponse(
            tool_calls=[
                ToolCall("write", "write_file", {"path": "main.py", "content": "answer = 42\n"})
            ]
        ),
        ModelResponse(text="Fixed the answer."),
    )
    agent = CodingAgent("fake/model", workspace=tmp_path, provider=provider, enable_shell=False)
    assert agent.run("Change the answer to 42") == "Fixed the answer."
    assert target.read_text() == "answer = 42\n"
    assert "answer = 41" in provider.requests[2][-1].content
    assert "main.py" in provider.requests[1][-1].content
    assert agent.last_result is not None
    assert len(agent.last_result.tool_calls) == 3


def test_shell_defaults_and_custom_prompt(tmp_path: Path) -> None:
    agent = CodingAgent("fake/model", tmp_path, provider=FakeProvider(), system_prompt="Custom")
    assert {schema.name for schema in agent._registry.schemas} == {
        "read_file",
        "write_file",
        "list_files",
        "shell",
    }
    assert agent.history[0].content == "Custom"
