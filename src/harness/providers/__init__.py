"""A small registry; custom providers implement BaseProvider."""

from collections.abc import Callable

from harness.exceptions import ConfigurationError
from harness.providers.base import BaseProvider
from harness.providers.openai import OpenAIProvider

ProviderFactory = Callable[..., BaseProvider]
_PROVIDERS: dict[str, ProviderFactory] = {"openai": OpenAIProvider}


def register_provider(name: str, factory: ProviderFactory, *, replace: bool = False) -> None:
    """Explicitly register a provider factory; no automatic discovery."""
    if not name or "/" in name or any(character.isspace() for character in name):
        raise ConfigurationError("Provider name must be nonempty without slashes or whitespace")
    if name in _PROVIDERS and not replace:
        raise ConfigurationError(f"Provider {name!r} is already registered")
    _PROVIDERS[name] = factory


def get_provider(
    model: str, api_key: str | None = None, *, temperature: float | None = None
) -> BaseProvider:
    name, separator, model_name = model.partition("/")
    if not separator or not model_name or name not in _PROVIDERS:
        raise ConfigurationError("Use a registered provider and model: 'provider/model-name'")
    return _PROVIDERS[name](model=model_name, api_key=api_key, temperature=temperature)


__all__ = ["BaseProvider", "OpenAIProvider", "get_provider", "register_provider"]
