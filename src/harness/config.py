"""Validated, per-agent configuration with explicit environment loading."""

from __future__ import annotations

import os
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator

from harness.exceptions import ConfigurationError

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class AgentConfig(BaseModel):
    """Immutable settings. Construct directly or use :meth:`from_env`."""

    model_config = ConfigDict(frozen=True, extra="forbid", hide_input_in_errors=True)

    model: str
    api_key: SecretStr | None = Field(default=None, repr=False, exclude=True)
    system_prompt: str | None = None
    max_steps: int = Field(default=20, gt=0, strict=True)
    temperature: float | None = Field(default=0.2, ge=0.0, le=2.0, allow_inf_nan=False)
    verbose: bool = False
    log_level: LogLevel = "WARNING"

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        provider, separator, model = value.partition("/")
        if not separator or not provider.strip() or not model.strip():
            raise ValueError("model must use the format 'provider/model-name'")
        if any(character.isspace() for character in value):
            raise ValueError("model must not contain whitespace")
        return value

    @classmethod
    def from_env(cls, **overrides: Any) -> AgentConfig:
        """Read supported variables at call time; explicit values take precedence.

        ``None`` retains environment defaults except for temperature, where it
        disables sampling parameters. Secrets are omitted from validation messages.
        """
        settings: dict[str, Any] = {}
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            settings["api_key"] = api_key
        max_steps = os.getenv("HARNESS_MAX_STEPS")
        if max_steps is not None:
            # Keep malformed environment values for the unified validation below.
            try:
                settings["max_steps"] = int(max_steps)
            except ValueError:
                settings["max_steps"] = max_steps
        log_level = os.getenv("HARNESS_LOG_LEVEL")
        if log_level is not None:
            settings["log_level"] = log_level.upper()
        settings.update(
            {
                key: value
                for key, value in overrides.items()
                if value is not None or key == "temperature"
            }
        )
        try:
            return cls(**settings)
        except ValidationError as error:
            details = "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}: {item['msg']}"
                for item in error.errors(include_input=False, include_url=False)
            )
            raise ConfigurationError(f"Invalid agent configuration: {details}") from None
