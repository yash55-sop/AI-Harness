# Getting started

Install Python 3.10+, then install from the repository until the PyPI release is live:

```bash
python -m pip install -e ".[openai]"
```

After publication, the equivalent command is:

```bash
python -m pip install "lightweight-ai-harness[openai]"
```

Set the API key in the current shell without putting it in source code:

```bash
# POSIX shell; replace the placeholder locally:
export OPENAI_API_KEY="your-key"
```

```powershell
# PowerShell; replace the placeholder locally:
$env:OPENAI_API_KEY = "your-key"
```

```python
from harness import Agent

with Agent("openai/gpt-4.1-mini") as agent:
    answer = agent.run("Explain binary search.")
    print(answer)
```

Choose a model available to your account that supports the Responses API.
For models without temperature support, pass `temperature=None`. Plain Agent
has no tools; it cannot read files or execute commands.

For an offline demonstration, run `python examples/offline_agent.py` after
installing the core package with `python -m pip install -e .`.

For a repository task, use CodingAgent or the CLI. Review the [security guide](security.md)
before enabling shell execution. `harness --read-only "Explain this repository"`
enables only read/list tools.
