# Lightweight AI Harness

```bash
# From this checkout (the initial PyPI upload is pending):
python -m pip install -e ".[openai]"
# After publication:
# python -m pip install "lightweight-ai-harness[openai]"
```

A small, synchronous Python harness for building tool-using AI agents. Python 3.10+
is supported. It provides a bounded agent loop, a replaceable model provider,
typed tools, conversation context, memory, structured logging, and a CLI.

## Quick start

Set `OPENAI_API_KEY` in your environment, then:

```python
from harness import Agent

with Agent(model="openai/gpt-4.1-mini") as agent:
    print(agent.run("Explain binary search."))
    print(agent.last_result.steps)
```

Construction makes no requests. `run()` returns a string and retains conversation
history; `last_result` contains usage, duration, steps, and tool calls. Use
`agent.reset()` for a fresh conversation. `temperature=None` omits sampling
parameters for models that do not accept them. Your model must support the Responses
API; model availability depends on your account.

The core package also works with your own provider without the OpenAI extra.
Tests and [the offline example](examples/offline_agent.py) need no API key.

## Agents and tools

Plain `Agent` has no tools. Enable only the operations your application needs:

```python
from harness import Agent
from harness.tools import ListFiles, ReadFile

with Agent(
    model="openai/gpt-4.1-mini",
    workspace=".",
    tools=[ReadFile(), ListFiles()],
) as agent:
    print(agent.run("Explain the architecture of this project."))
```

An Agent workspace binds built-in filesystem tools to that resolved directory
without mutating shared tool instances. Relative paths use that workspace.
Custom tools are trusted Python code and must implement their own access controls.

## CodingAgent

```python
from harness import CodingAgent

with CodingAgent(model="openai/gpt-4.1-mini", workspace="./project") as agent:
    print(agent.run("Find why the tests fail and fix the issue."))
```

CodingAgent enables ReadFile, WriteFile, ListFiles, and Shell. It uses the same
runtime as Agent. Set `enable_shell=False` to remove command execution.

**Shell access grants the model command execution with your process permissions.**
A working directory is not an OS sandbox. Use a container or other isolation for
untrusted code, and review changes before applying them to important workspaces.

## Creating custom tools

```python
from harness import Agent
from harness.tools import Tool


class Add(Tool):
    name = "add"
    description = "Add two integers"

    def run(self, a: int, b: int) -> int:
        return a + b


with Agent(model="openai/gpt-4.1-mini", tools=[Add()]) as agent:
    print(agent.run("Use add to calculate 13 + 29."))
```

Input schemas are derived from type hints. Alternatively declare
`input_model = YourPydanticModel`. Inputs are validated strictly before execution;
unknown fields, unknown tools, and duplicate names raise harness errors.
Outputs must be strings or JSON-serializable values. See [the tool guide](docs/tools.md).

## Providers

The optional OpenAI adapter uses the Responses API with `store=False`, preserves
reasoning continuation data, normalizes responses, and retries transient network,
rate-limit, timeout, and server errors with bounded exponential backoff. Credentials,
invalid requests, and unsupported models are not retried.

Inject `provider=YourProvider()` or register a named factory explicitly.
See [the provider guide](docs/providers.md) for the contract and HTTP mocking examples.

## Configuration

| Setting | Default | Environment |
| --- | --- | --- |
| model | Required in Python | HARNESS_MODEL in CLI only |
| api_key | None | OPENAI_API_KEY |
| max_steps | 20 | HARNESS_MAX_STEPS |
| temperature | 0.2 in Python; omitted in CLI | None |
| system_prompt | None; coding prompt in CodingAgent | None |
| verbose | False | None |
| log_level | WARNING | HARNESS_LOG_LEVEL |
| max_context_messages | 100 | None |
| max_context_chars | 100,000 | None |
| max_tool_output | 20,000 characters | None |

Explicit arguments override environment defaults. `temperature=None` disables the
sampling parameter. Configuration is immutable and scoped to each agent. API keys
are redacted and excluded from configuration dumps.

Context discards complete older user turns to stay within its message/character
budgets while retaining the system prompt and active turn. Character budgets
approximate context size; they are not exact model token limits. An oversized
active turn raises ContextLimitError. Memory is separate from model context and
is never sent to the model automatically.

## CLI

```bash
harness --model openai/gpt-4.1-mini --workspace . "Explain this project"
harness --verbose "Run the tests and fix failures"
harness --read-only "Explain the authentication system"
harness --no-shell "Update the documentation"
harness --max-steps 10 "Inspect this repository"
python -m harness --help
```

CLI defaults to `openai/gpt-4.1-mini` and CodingAgent: **writes and shell are enabled**.
Use `--read-only` for only ReadFile/ListFiles, or `--no-shell` for filesystem edits
without commands. Progress goes to stderr; the final answer goes to stdout.
Credentials are read from the environment, not passed as command-line arguments.

## Errors and observability

HarnessError is the common exception base. Specific errors include
ConfigurationError, ProviderError, AuthenticationError, ToolError,
ToolNotFoundError, ToolValidationError, DuplicateToolError, MaxStepsExceeded,
and ContextLimitError. Import specific errors from `harness.exceptions`.

Failed runs restore prior conversation history; already executed tool side effects
remain. A batch of tool calls is fully validated before execution. The first
execution failure ends the run.

`verbose=True` emits structured event metadata through standard logging without
logging prompts, arguments, tool outputs, HTTP bodies, or credentials. Supply
`logger=` to integrate with application logging. See [the agent guide](docs/agents.md).

## Security

Filesystem tools reject paths resolving outside the workspace, including escaping
symlinks, Windows junctions, and NTFS alternate streams. WriteFile rejects hard-linked
targets. ReadFile limits bytes, ListFiles limits entries, and Shell limits captured
output and elapsed execution time.

These are application checks for a trusted local filesystem, not protection against
hostile concurrent filesystem changes. Shell, custom tools, and hard-linked reads
have broader capabilities. Tools can send file contents and command output to the
model; exclude sensitive files and avoid exposing credentials in commands.
See [security details](docs/security.md).

## Examples and documentation

- [Getting started](docs/getting-started.md)
- [Agent lifecycle and metadata](docs/agents.md)
- [Tool creation](docs/tools.md)
- [Provider extension](docs/providers.md)
- [Basic agent](examples/basic_agent.py), [coding agent](examples/coding_agent.py),
  [custom tool](examples/custom_tool.py), [offline agent](examples/offline_agent.py)
- [CLI examples](examples/cli_example.md)
- [Milestone report and tree](docs/milestones.md)
- [Release and trusted publishing](docs/releasing.md)

## Contributing

```bash
python -m venv .venv
# POSIX: source .venv/bin/activate
# PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev,openai]"
python -m ruff check .
python -m ruff format --check .
python -m mypy
python -m pytest --cov=harness --cov-branch --cov-report=term-missing
python -m build
python -m twine check --strict dist/*
python scripts/verify_wheel.py
```

CI checks Python 3.10–3.13 on Linux and Windows. Unit tests do not use paid APIs.
The integration test additionally requires `HARNESS_RUN_INTEGRATION=1` and
`OPENAI_API_KEY`; run it explicitly with `pytest -m integration`.

## License

[MIT](LICENSE).
