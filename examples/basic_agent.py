"""Requires the OpenAI extra and OPENAI_API_KEY."""

from harness import Agent

if __name__ == "__main__":
    with Agent("openai/gpt-4.1-mini") as agent:
        print(agent.run("Explain binary search in three sentences."))
