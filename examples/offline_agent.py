"""Run the entire tool loop without credentials or network requests."""

from collections.abc import Sequence

from harness import Agent
from harness.models import Message, ModelResponse, ToolCall, ToolSchema
from harness.providers import BaseProvider
from harness.tools import Tool


class Add(Tool):
    name = "add"
    description = "Add two integers"

    def run(self, a: int, b: int) -> int:
        return a + b


class DemoProvider(BaseProvider):
    def generate(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolSchema] | None = None,
    ) -> ModelResponse:
        if messages[-1].role == "tool":
            return ModelResponse(text=f"The answer is {messages[-1].content}.")
        return ModelResponse(tool_calls=[ToolCall("addition", "add", {"a": 13, "b": 29})])


if __name__ == "__main__":
    with Agent("demo/model", provider=DemoProvider(), tools=[Add()]) as agent:
        print(agent.run("Add 13 and 29."))
        if agent.last_result is not None:
            print(f"Completed in {agent.last_result.steps} steps")
