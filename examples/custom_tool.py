"""Create a typed arithmetic tool without eval or executable expressions."""

from harness import Agent
from harness.tools import Tool


class Add(Tool):
    name = "add"
    description = "Add two integers"

    def run(self, a: int, b: int) -> int:
        return a + b


if __name__ == "__main__":
    with Agent("openai/gpt-4.1-mini", tools=[Add()]) as agent:
        print(agent.run("Use add to calculate 13 + 29."))
