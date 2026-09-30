"""Configuration validation, precedence, isolation, and secret handling."""

import pytest
from pydantic import ValidationError

from harness import Agent, AgentConfig, ConfigurationError


def test_defaults() -> None:
    config = AgentConfig(model="openai/example-model")
    assert config.max_steps == 20
    assert config.temperature == 0.2
    assert config.log_level == "WARNING"
    assert config.verbose is False
    assert config.system_prompt is None


def test_environment_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")
    monkeypatch.setenv("HARNESS_MAX_STEPS", "7")
    monkeypatch.setenv("HARNESS_LOG_LEVEL", "debug")
    config = Agent("openai/example-model").config
    assert config.max_steps == 7
    assert config.log_level == "DEBUG"
    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "environment-secret"


def test_explicit_settings_override_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "environment-secret")
    monkeypatch.setenv("HARNESS_MAX_STEPS", "bad-value")
    config = Agent("openai/example-model", api_key="explicit-secret", max_steps=4).config
    assert config.max_steps == 4
    assert config.api_key is not None
    assert config.api_key.get_secret_value() == "explicit-secret"


def test_environment_is_read_for_each_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    first = Agent("openai/example-model")
    monkeypatch.setenv("HARNESS_MAX_STEPS", "9")
    second = Agent("openai/example-model")
    assert first.config.max_steps == 20
    assert second.config.max_steps == 9


@pytest.mark.parametrize("model", ["", "openai", "/model", "openai/", "open ai/model"])
def test_invalid_model(model: str) -> None:
    with pytest.raises(ConfigurationError, match="model"):
        Agent(model)


@pytest.mark.parametrize("value", [0, -1, True, 1.5, "5"])
def test_invalid_step_limit(value: object) -> None:
    with pytest.raises(ConfigurationError, match="max_steps"):
        AgentConfig.from_env(model="openai/example-model", max_steps=value)


@pytest.mark.parametrize("value", ["0", "-2", "abc", "", "2.5"])
def test_invalid_environment_limit(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_MAX_STEPS", value)
    with pytest.raises(ConfigurationError, match="max_steps"):
        Agent("openai/example-model")


@pytest.mark.parametrize("value", [-0.1, 2.1, float("nan"), float("inf")])
def test_invalid_temperature(value: float) -> None:
    with pytest.raises(ConfigurationError, match="temperature"):
        Agent("openai/example-model", temperature=value)


def test_invalid_log_level(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HARNESS_LOG_LEVEL", "loud")
    with pytest.raises(ConfigurationError, match="log_level"):
        Agent("openai/example-model")


def test_secrets_are_omitted_from_representations() -> None:
    config = AgentConfig.from_env(model="openai/example-model", api_key="private-test-key")
    assert "private-test-key" not in repr(config)
    assert "private-test-key" not in str(config)
    assert "api_key" not in config.model_dump()
    assert "private-test-key" not in config.model_dump_json()


def test_validation_error_does_not_expose_input() -> None:
    with pytest.raises(ConfigurationError) as caught:
        AgentConfig.from_env(model="openai/example-model", api_key={"key": "private-test-key"})
    assert "private-test-key" not in str(caught.value)
    assert caught.value.__cause__ is None


def test_configuration_is_immutable() -> None:
    config = AgentConfig(model="openai/example-model")
    with pytest.raises(ValidationError, match="frozen"):
        config.max_steps = 3


def test_unknown_setting_is_rejected() -> None:
    with pytest.raises(ConfigurationError, match="Extra inputs"):
        AgentConfig.from_env(model="openai/example-model", typo=True)
