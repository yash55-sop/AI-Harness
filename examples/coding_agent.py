"""Inspect and edit a workspace; shell execution is enabled."""

from harness import CodingAgent

if __name__ == "__main__":
    with CodingAgent("openai/gpt-4.1-mini", workspace=".") as agent:
        print(agent.run("Inspect this project and propose a small improvement."))
