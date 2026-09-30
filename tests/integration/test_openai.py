"""Opt-in paid API smoke test, never enabled just by the presence of a key."""

import os

import pytest

from harness import Agent

pytestmark = pytest.mark.integration


def test_live_openai_response() -> None:
    if os.getenv("HARNESS_RUN_INTEGRATION") != "1" or not os.getenv("OPENAI_API_KEY"):
        pytest.skip("Set HARNESS_RUN_INTEGRATION=1 and OPENAI_API_KEY to opt into paid tests")
    with Agent(
        os.getenv("HARNESS_TEST_MODEL", "openai/gpt-4.1-mini"), temperature=None, max_steps=2
    ) as agent:
        assert agent.run("Reply with a short greeting.").strip()
