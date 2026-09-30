# Milestone report

## Status

Milestones 1–9 are implemented. Milestone 10 build, validation, wheel installation,
and trusted-publishing workflow are complete; the first public PyPI upload still
requires a trusted publisher in the release owner's PyPI account.

Repository: [yash55-sop/AI-Harness](https://github.com/yash55-sop/AI-Harness).

## Decisions and verification by milestone

| Milestone | Architecture and new files | Verification |
| --- | --- | --- |
| 1 — Skeleton | Hatchling src layout, AgentConfig, base exceptions, typed exports, initial CI | Editable install; 39 initial tests |
| 2 — Provider | BaseProvider, OpenAIProvider, explicit registry, normalized Message/ModelResponse/ToolCall/Usage | 73 stage tests; HTTP mocks for retries, credentials, request encoding and malformed responses |
| 3 — Tools | Tool, ToolRegistry; inferred or explicit Pydantic input schemas | 88 stage tests; strict inputs, duplicates, schema generation and failure translation |
| 4 — Loop | Shared Agent runtime, Context, Memory, structured logging, RunResult metadata | 112 stage tests; calculator loop, step limits, complete-turn trimming and failure recovery |
| 5 — Coding tools | WorkspaceTool, ReadFile, WriteFile, ListFiles, Shell | 142 stage tests; traversal, hard links, UTF-8, output bounds and shell timeout |
| 6 — CodingAgent | A convenience subclass using the same Agent runtime | 144 stage tests; offline list → read → write → answer workflow |
| 7 — CLI | Typer entry point and python -m harness; read-only/no-shell capability options | CLI parsing, credentials, stdout/stderr, help, version and environment tests |
| 8 — Quality | Ruff, strict Mypy, coverage threshold, Linux/Windows Python 3.10–3.13 CI | Final local suite: 159 passed, 2 skipped on each of 3.10/3.11/3.12/3.13; 96.54% coverage on 3.12 |
| 9 — Documentation | README, agent/tool/provider/security/release guides, four Python examples | Offline example executes a tool call without credentials; guides match implemented APIs |
| 10 — Release preparation | Package URLs, metadata 2.4, version/tag check, strict Twine check, independent wheel smoke test, OIDC publish workflow | sdist and wheel build; strict metadata check and independent wheel install pass; upload pending PyPI setup |

The optional live API test is skipped unless explicitly enabled with both
HARNESS_RUN_INTEGRATION=1 and OPENAI_API_KEY. The symlink test is skipped on this
Windows session because creating symlinks is not permitted. A separate Windows
junction escape test passes locally. Linux CI is configured to exercise symlinks.
GitHub CI results are tracked in the repository's Actions page.

Agent.run() keeps the milestone 1 string-return contract; successful metadata is
available via last_result. Providers own HTTP schemas and opaque continuation
state. Tools own implementation and validation. Each Agent owns its tools, context,
memory, limits, and logging settings. Named provider registration is an explicit
process-wide operation; there is no discovery or implicit plugin framework.

Plain Agent starts with no tools. CodingAgent and the CLI explicitly enable coding
tools, including shell by default. Filesystem containment is checked after path
resolution. Shell cwd/timeout/output controls do not create an OS sandbox.
See [security](security.md) for the precise boundaries.

No actual API response was tested because no API key was configured. No PyPI
credentials or trusted publisher were available during local implementation.

## Final file tree

```text
.
├── .gitattributes
├── .github/workflows/
│   ├── test.yml
│   └── publish.yml
├── .gitignore
├── CHANGELOG.md
├── LICENSE
├── README.md
├── pyproject.toml
├── docs/
│   ├── agents.md
│   ├── getting-started.md
│   ├── milestones.md
│   ├── providers.md
│   ├── releasing.md
│   ├── security.md
│   └── tools.md
├── examples/
│   ├── basic_agent.py
│   ├── coding_agent.py
│   ├── custom_tool.py
│   ├── offline_agent.py
│   └── cli_example.md
├── scripts/
│   ├── check_release.py
│   └── verify_wheel.py
├── src/harness/
│   ├── __init__.py
│   ├── __main__.py
│   ├── agent.py
│   ├── coding.py
│   ├── config.py
│   ├── context.py
│   ├── exceptions.py
│   ├── logging.py
│   ├── memory.py
│   ├── models.py
│   ├── py.typed
│   ├── cli/{__init__.py,main.py}
│   ├── providers/{__init__.py,base.py,openai.py}
│   └── tools/{__init__.py,base.py,filesystem.py,shell.py}
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fakes.py
    ├── test_agent.py
    ├── test_cli.py
    ├── test_coding.py
    ├── test_config.py
    ├── test_context.py
    ├── test_filesystem.py
    ├── test_junction.py
    ├── test_loop.py
    ├── test_memory.py
    ├── test_provider.py
    ├── test_release.py
    ├── test_shell.py
    ├── test_tools.py
    └── integration/test_openai.py
```

Local build artifacts are in dist/ and ignored by Git. Local virtual environments
and development caches are also ignored.
