"""An optional HTTP adapter for the OpenAI Responses API."""

from __future__ import annotations

import json
import math
import os
import time
from collections.abc import Callable, Sequence
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from pydantic import SecretStr

from harness.exceptions import AuthenticationError, ConfigurationError, ProviderError
from harness.models import Message, ModelResponse, ToolCall, ToolSchema, Usage
from harness.providers.base import BaseProvider

if TYPE_CHECKING:
    import httpx


class OpenAIProvider(BaseProvider):
    """Use stateless Responses requests with bounded exponential retries.

    Set temperature=None for models that do not accept sampling parameters.
    Inject an httpx Client with MockTransport for tests. Injected clients remain
    the caller's responsibility; close() only closes an owned client.
    """

    def __init__(
        self,
        model: str,
        api_key: str | None = None,
        *,
        temperature: float | None = None,
        timeout: float = 60.0,
        max_retries: int = 2,
        client: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not model or any(character.isspace() for character in model):
            raise ConfigurationError("OpenAI model must be a nonempty name without whitespace")
        if not math.isfinite(timeout) or timeout <= 0:
            raise ConfigurationError("Provider timeout must be finite and positive")
        if isinstance(max_retries, bool) or not isinstance(max_retries, int) or max_retries < 0:
            raise ConfigurationError("max_retries must be a nonnegative integer")
        if temperature is not None and (
            not math.isfinite(temperature) or not 0 <= temperature <= 2
        ):
            raise ConfigurationError("temperature must be between 0 and 2, or None")
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key or not key.strip():
            raise AuthenticationError(
                "Set OPENAI_API_KEY or pass api_key to use the OpenAI provider"
            )
        try:
            import httpx
        except ImportError:
            raise ConfigurationError(
                'Install the OpenAI extra: pip install "lightweight-ai-harness[openai]"'
            ) from None
        self.model = model
        self._api_key = SecretStr(key)
        self.temperature = temperature
        self.timeout = timeout
        self.max_retries = max_retries
        self._sleep = sleep
        self._owned_client = client is None
        self._client = client if client is not None else httpx.Client()

    def generate(
        self, messages: Sequence[Message], tools: Sequence[ToolSchema] | None = None
    ) -> ModelResponse:
        import httpx

        body: dict[str, Any] = {
            "model": self.model,
            "input": self._encode_messages(messages),
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        if self.temperature is not None:
            body["temperature"] = self.temperature
        if tools:
            body["tools"] = [
                {
                    "type": "function",
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "strict": False,
                }
                for tool in tools
            ]
        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.post(
                    "https://api.openai.com/v1/responses",
                    headers={"Authorization": f"Bearer {self._api_key.get_secret_value()}"},
                    json=body,
                    timeout=self.timeout,
                )
            except (httpx.TimeoutException, httpx.TransportError):
                if attempt < self.max_retries:
                    self._sleep(float(2**attempt))
                    continue
                raise ProviderError(
                    "OpenAI request failed after transient network errors"
                ) from None
            if response.status_code in (401, 403):
                raise AuthenticationError("OpenAI rejected the credentials or account permissions")
            if response.status_code in (408, 429) or response.status_code >= 500:
                if attempt < self.max_retries:
                    self._sleep(float(2**attempt))
                    continue
                raise ProviderError(
                    f"OpenAI transient HTTP {response.status_code}; retries exhausted"
                )
            if response.is_error:
                raise ProviderError(
                    f"OpenAI HTTP {response.status_code}; check model and request configuration"
                )
            try:
                return self.normalize(response.json())
            except (ValueError, TypeError, KeyError):
                raise ProviderError("OpenAI returned a malformed response") from None
        raise AssertionError("unreachable")  # pragma: no cover

    @staticmethod
    def _encode_messages(messages: Sequence[Message]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for message in messages:
            if message.role == "tool":
                if not message.call_id:
                    raise ProviderError("Tool result is missing its call ID")
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": message.call_id,
                        "output": message.content,
                    }
                )
            elif message.role == "assistant" and "openai" in message.provider_data:
                items.extend(deepcopy(message.provider_data["openai"]))
            else:
                if message.content or not message.tool_calls:
                    items.append({"role": message.role, "content": message.content})
                for call in message.tool_calls:
                    items.append(
                        {
                            "type": "function_call",
                            "call_id": call.id,
                            "name": call.name,
                            "arguments": json.dumps(call.arguments, allow_nan=False),
                        }
                    )
        return items

    @staticmethod
    def normalize(payload: Any) -> ModelResponse:
        """Reject malformed/incomplete responses before exposing tool requests."""
        if not isinstance(payload, dict) or not isinstance(payload.get("output"), list):
            raise ProviderError("OpenAI returned an invalid response envelope")
        status = payload.get("status")
        if status != "completed":
            raise ProviderError("OpenAI did not complete the response; no tools were executed")
        texts: list[str] = []
        calls: list[ToolCall] = []
        ids: set[str] = set()
        try:
            for item in payload["output"]:
                if item["type"] == "function_call":
                    call_id, name = item["call_id"], item["name"]
                    arguments = json.loads(item["arguments"])
                    if (
                        not isinstance(call_id, str)
                        or not call_id
                        or call_id in ids
                        or not isinstance(name, str)
                        or not name
                        or not isinstance(arguments, dict)
                    ):
                        raise ValueError("Invalid tool call")
                    ids.add(call_id)
                    calls.append(ToolCall(call_id, name, arguments))
                elif item["type"] == "message":
                    for part in item["content"]:
                        if part["type"] == "output_text":
                            if not isinstance(part["text"], str):
                                raise ValueError("Invalid text")
                            texts.append(part["text"])
                        elif part["type"] == "refusal":
                            texts.append(str(part["refusal"]))
                elif item["type"] != "reasoning":
                    raise ValueError("Unsupported response item")
            raw_usage = payload.get("usage")
            usage = None
            if raw_usage is not None:
                input_tokens, output_tokens = raw_usage["input_tokens"], raw_usage["output_tokens"]
                if any(
                    type(value) is not int or value < 0 for value in (input_tokens, output_tokens)
                ):
                    raise ValueError("Invalid token usage")
                usage = Usage(input_tokens, output_tokens)
        except (KeyError, TypeError, ValueError):
            raise ProviderError("OpenAI returned malformed output items or usage") from None
        return ModelResponse(
            text="".join(texts) or None,
            tool_calls=calls,
            usage=usage,
            finish_reason=status,
            provider_data={"openai": deepcopy(payload["output"])},
        )

    def close(self) -> None:
        if self._owned_client:
            self._client.close()
