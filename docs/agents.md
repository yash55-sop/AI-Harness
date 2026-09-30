# Agents

Agent owns the loop, tool registry, Context, application Memory, and last run metadata.
Providers own requests and response normalization. Tools own their implementations.
The runtime is synchronous; use a separate Agent per concurrent conversation.

```python
from harness import Agent, HarnessError

with Agent("openai/gpt-4.1-mini", max_steps=10, verbose=True) as agent:
    try:
        print(agent.run("Explain quicksort."))
        print(agent.run("Compare it with merge sort."))
        result = agent.last_result
        if result is not None:
            print(result.steps, result.usage, result.duration)
        agent.reset()
    except HarnessError as error:
        print(f"Agent failed: {error}")
```

Each step is one provider request. A tool-request step validates the full batch,
executes each tool sequentially, appends observations, and requests another response.
The first final text response ends the run. Tool/provider failures and exhaustion
raise harness exceptions. No tool approval policy is implemented in v0.1.

Failed runs restore prior conversation history, but cannot undo filesystem edits or
commands already executed. `last_result` becomes None when a new run starts and is
populated only on success. Tool call metadata includes arguments: treat history and
metadata as potentially sensitive even though standard logs omit them.

Context returns defensive message copies. It keeps the system prompt and newest
complete user turns, dropping older turns to meet `max_context_messages` and
`max_context_chars`. It raises ContextLimitError if the active turn cannot fit.
Character limits are approximate and include opaque provider continuation data;
an API can still reject an input exceeding its token window.

Memory supports `get`, `set`, and `delete`. It is separate from the conversation,
survives reset, and is not automatically exposed to models:

```python
from harness import InMemoryMemory

memory = InMemoryMemory()
memory.set("project", "demo")
assert memory.get("project") == "demo"
memory.delete("project")
```

`verbose=True` adds a private stderr logger emitting JSON event metadata. The library
does not configure root logging. Without verbose mode, the named `harness.agent`
logger follows your application logging configuration; `HARNESS_LOG_LEVEL` sets the
private verbose logger's threshold (WARNING defaults to INFO when verbose is enabled).
Inject a logger for custom handlers. No request or tool payloads are logged.

Use the context manager or `close()` to release providers created by Agent. Injected
providers and HTTP clients remain caller-owned. `add_tool` registers additional tools
between runs; duplicate names are errors. Reset, close, recursive run, and tool changes
are rejected during an active run.
