# Providers

BaseProvider accepts normalized Message objects and optional ToolSchema objects and
returns ModelResponse. Provider-specific SDK objects stay inside the adapter.

```python
from harness import Agent
from harness.models import ModelResponse
from harness.providers import BaseProvider


class FixedProvider(BaseProvider):
    def generate(self, messages, tools=None):
        return ModelResponse(text="Hello from my provider")


with Agent("custom/model", provider=FixedProvider()) as agent:
    assert agent.run("hello") == "Hello from my provider"
```

This injected provider needs no credentials and is caller-owned. Named resolution
uses an explicit registry. Factories accept `model`, `api_key`, and `temperature`:

```python
from harness.providers import register_provider

register_provider("fixed", lambda **settings: FixedProvider())
with Agent("fixed/demo") as agent:
    print(agent.run("hello"))
```

Registration is an intentional process-wide operation. Duplicate names are rejected
unless `replace=True`; there is no automatic provider discovery. Each Agent still
creates its own provider, tools, context, and memory.

OpenAIProvider uses HTTPX as an optional dependency, not the SDK:

```python
from harness.providers import OpenAIProvider

provider = OpenAIProvider("gpt-4.1-mini", temperature=None, timeout=60, max_retries=2)
try:
    with Agent("openai/gpt-4.1-mini", provider=provider) as agent:
        print(agent.run("hello"))
finally:
    provider.close()
```

The adapter uses [the Responses API](https://developers.openai.com/api/docs/guides/migrate-to-responses)
and [function calls](https://developers.openai.com/api/docs/guides/function-calling).
It sends `store=False` and requests encrypted reasoning continuation data. The data
is kept opaquely in Message.provider_data so subsequent tool turns retain needed
provider state. Stateless requests do not imply that the provider has no applicable
data-retention policies.

Function schemas use `strict=False` to preserve optional/default inputs; strict local
validation still runs before execution. Returned function arguments must decode to
an object. Duplicate call IDs, invalid usage, unsupported output items, and incomplete
responses raise ProviderError before tools execute. Authentication failures raise
AuthenticationError. HTTP 408, 429, 5xx and transient network failures are retried;
other request errors are not. Default backoff waits 1 then 2 seconds for three total
attempts. Provider response bodies and transport exception text are excluded from errors.

Unit tests use `httpx.MockTransport` to exercise the full request/response path. The
optional live test requires both `HARNESS_RUN_INTEGRATION=1` and `OPENAI_API_KEY`.
