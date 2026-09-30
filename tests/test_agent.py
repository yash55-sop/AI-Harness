"""Package and Agent skeleton contracts."""

from importlib.metadata import version

import pytest

from harness import Agent, ConfigurationError, HarnessError, __version__
from harness.models import ModelResponse
from tests.fakes import FakeProvider


def test_package_version_matches_metadata() -> None:
    assert version("lightweight-ai-harness") == __version__


def test_agent_can_be_created_without_credentials() -> None:
    agent = Agent(model="openai/example-model")
    assert agent.config.model == "openai/example-model"
    assert agent.config.max_steps == 20
    assert agent.config.api_key is None


def test_agent_forwards_configuration() -> None:
    agent = Agent(
        model="custom/example-model",
        api_key="test-secret",
        system_prompt="Be concise.",
        max_steps=3,
        verbose=True,
        temperature=0.5,
    )
    assert agent.config.system_prompt == "Be concise."
    assert agent.config.max_steps == 3
    assert agent.config.verbose is True
    assert agent.config.temperature == 0.5
    assert agent.config.api_key is not None
    assert agent.config.api_key.get_secret_value() == "test-secret"


def test_agent_settings_are_independent() -> None:
    first = Agent("openai/first", max_steps=2)
    second = Agent("openai/second")
    assert first.config.max_steps == 2
    assert second.config.max_steps == 20


def test_run_returns_provider_answer() -> None:
    provider = FakeProvider(ModelResponse(text="Hello"))
    assert Agent("openai/example-model", provider=provider).run("hello") == "Hello"
    assert provider.requests[0][0].content == "hello"


@pytest.mark.parametrize("task", ["", " ", "\n\t", None, 42])
def test_run_rejects_invalid_task(task: object) -> None:
    with pytest.raises(ConfigurationError, match="nonempty string"):
        Agent("openai/example-model").run(task)  # type: ignore[arg-type]


def test_configuration_error_is_a_harness_error() -> None:
    assert issubclass(ConfigurationError, HarnessError)
