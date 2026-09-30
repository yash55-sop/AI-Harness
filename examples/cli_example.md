# CLI

```bash
python -m pip install -e ".[openai]"
harness --version
harness --help
harness --read-only --workspace . "Explain this repository"
harness --no-shell --workspace . "Update the README introduction"
harness --verbose --max-steps 10 "Run the tests and fix the failure"
```

Set OPENAI_API_KEY in your environment first. --read-only enables only read/list
tools. The default mode grants writes and shell execution; --no-shell disables
commands but still permits file writes. --model overrides HARNESS_MODEL and the
default openai/gpt-4.1-mini. For a model accepting sampling parameters, pass
--temperature 0.2; otherwise it is omitted.
