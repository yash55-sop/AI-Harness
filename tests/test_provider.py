"""Provider contract, request serialization, normalization, and retry behavior."""

import json
from typing import Any

import httpx
import pytest

from harness import Agent
from harness.exceptions import AuthenticationError, ConfigurationError, ProviderError
from harness.models import Message, ModelResponse, ToolCall, ToolSchema, Usage
from harness.providers import OpenAIProvider, get_provider, register_provider
from tests.fakes import FakeProvider


def payload(*output: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "completed",
        "output": list(output),
        "usage": {"input_tokens": 5, "output_tokens": 2},
    }


def text_item(text: str = "Hello") -> dict[str, Any]:
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text}],
    }


def test_request_and_normalization() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json=payload(text_item()))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenAIProvider("example-model", "test-key", client=client, temperature=0.2)
        result = provider.generate([Message("system", "Be helpful"), Message("user", "hi")])
    body = json.loads(requests[0].content)
    assert body["model"] == "example-model"
    assert body["store"] is False
    assert body["temperature"] == 0.2
    assert body["input"][0]["role"] == "system"
    assert result.text == "Hello"
    assert result.usage == Usage(5, 2)
    assert result.finish_reason == "completed"


def test_normalizes_tools_and_preserves_reasoning() -> None:
    raw = payload(
        {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "opaque"},
        {"type": "function_call", "call_id": "call_1", "name": "add", "arguments": '{"a": 1}'},
    )
    result = OpenAIProvider.normalize(raw)
    assert result.has_tool_calls
    assert result.tool_calls == [ToolCall("call_1", "add", {"a": 1})]
    messages = [
        Message("assistant", tool_calls=result.tool_calls, provider_data=result.provider_data),
        Message("tool", "2", call_id="call_1"),
    ]
    encoded = OpenAIProvider._encode_messages(messages)
    assert encoded[:2] == raw["output"]
    assert encoded[-1] == {"type": "function_call_output", "call_id": "call_1", "output": "2"}


def test_generic_tool_history_encoding() -> None:
    items = OpenAIProvider._encode_messages(
        [
            Message("assistant", "Checking", [ToolCall("c1", "add", {"a": 1})]),
            Message("tool", "2", call_id="c1"),
        ]
    )
    assert items[0] == {"role": "assistant", "content": "Checking"}
    assert json.loads(items[1]["arguments"]) == {"a": 1}
    with pytest.raises(ProviderError, match="call ID"):
        OpenAIProvider._encode_messages([Message("tool", "2")])


def test_tool_schema_is_converted_and_temperature_omitted() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert "temperature" not in body
        assert body["tools"][0]["name"] == "add"
        assert body["tools"][0]["strict"] is False
        return httpx.Response(200, json=payload(text_item()))

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        provider = OpenAIProvider("example", "key", client=client)
        provider.generate([Message("user", "hi")], [ToolSchema("add", "Add", {"type": "object"})])
        provider.close()
        assert not client.is_closed


@pytest.mark.parametrize("status", [401, 403, 400, 404, 422])
def test_permanent_errors_are_not_retried(status: int) -> None:
    attempts = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: attempts.append(1) or httpx.Response(status, text="secret")
        )
    ) as client:
        provider = OpenAIProvider("example", "key", client=client)
        expected = AuthenticationError if status in (401, 403) else ProviderError
        with pytest.raises(expected) as caught:
            provider.generate([Message("user", "hi")])
    assert len(attempts) == 1
    assert "secret" not in str(caught.value)


@pytest.mark.parametrize("status", [408, 429, 500, 503])
def test_transient_errors_retry_with_backoff(status: int) -> None:
    statuses = [status, status, 200]
    delays = []
    with httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(statuses.pop(0), json=payload(text_item()))
        )
    ) as client:
        provider = OpenAIProvider("example", "key", client=client, sleep=delays.append)
        assert provider.generate([Message("user", "hi")]).text == "Hello"
    assert delays == [1.0, 2.0]


def test_retries_exhausted() -> None:
    with httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(429))) as client:
        provider = OpenAIProvider("example", "key", client=client, sleep=lambda delay: None)
        with pytest.raises(ProviderError, match="exhausted"):
            provider.generate([Message("user", "hi")])


def test_network_retry_and_exhaustion() -> None:
    attempts = []

    def fail(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        raise httpx.ReadTimeout("private-detail", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        provider = OpenAIProvider("example", "key", client=client, sleep=lambda delay: None)
        with pytest.raises(ProviderError, match="network") as caught:
            provider.generate([Message("user", "hi")])
    assert len(attempts) == 3
    assert "private-detail" not in str(caught.value)


@pytest.mark.parametrize(
    "raw",
    [
        {},
        [],
        {"status": "incomplete", "output": []},
        payload({"type": "function_call", "call_id": "c1", "name": "x", "arguments": "[]"}),
        payload({"type": "function_call", "call_id": "c1", "name": "x", "arguments": "bad"}),
        payload({"type": "message", "content": [{"type": "output_text", "text": 42}]}),
        payload({"type": "unknown"}),
        {"status": "completed", "output": [], "usage": {"input_tokens": -1, "output_tokens": 0}},
    ],
)
def test_rejects_malformed_response(raw: Any) -> None:
    with pytest.raises(ProviderError):
        OpenAIProvider.normalize(raw)


def test_non_json_response() -> None:
    with httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(200, text="bad"))
    ) as client:
        provider = OpenAIProvider("example", "key", client=client)
        with pytest.raises(ProviderError, match="malformed"):
            provider.generate([Message("user", "hi")])


def test_refusal_and_missing_usage() -> None:
    result = OpenAIProvider.normalize(
        {
            "status": "completed",
            "output": [
                {"type": "message", "content": [{"type": "refusal", "refusal": "Cannot help"}]}
            ],
        }
    )
    assert result.text == "Cannot help"
    assert result.usage is None


def test_missing_credentials_and_environment_key(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(AuthenticationError, match="OPENAI_API_KEY"):
        OpenAIProvider("example")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    provider = OpenAIProvider("example")
    provider.close()
    assert provider._client.is_closed


@pytest.mark.parametrize(
    "kwargs",
    [
        {"model": ""},
        {"timeout": 0},
        {"timeout": float("nan")},
        {"max_retries": -1},
        {"max_retries": True},
        {"temperature": 3},
    ],
)
def test_invalid_provider_configuration(kwargs: dict[str, Any]) -> None:
    settings = {"model": "example", "api_key": "key", **kwargs}
    with pytest.raises(ConfigurationError):
        OpenAIProvider(**settings)


def test_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    import harness.providers as providers

    monkeypatch.setattr(providers, "_PROVIDERS", dict(providers._PROVIDERS))
    register_provider("fake", lambda **kwargs: FakeProvider())
    assert get_provider("fake/example").generate([]).text == "Hello"
    with pytest.raises(ConfigurationError, match="already"):
        register_provider("fake", lambda **kwargs: FakeProvider())
    register_provider("fake", lambda **kwargs: FakeProvider(), replace=True)
    with pytest.raises(ConfigurationError):
        register_provider("bad/name", lambda **kwargs: FakeProvider())
    with pytest.raises(ConfigurationError):
        get_provider("missing/example")


def test_agent_system_prompt_and_empty_answer() -> None:
    provider = FakeProvider(ModelResponse(text="yes"))
    agent = Agent("fake/example", provider=provider, system_prompt="Be concise")
    assert agent.run("hi") == "yes"
    assert provider.requests[0][0] == Message("system", "Be concise")
    with pytest.raises(ProviderError, match="no text"):
        Agent("fake/example", provider=FakeProvider(ModelResponse())).run("hi")
