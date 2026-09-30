# Tools

Subclass Tool and give each input a type annotation:

```python
from harness.tools import Tool


class Add(Tool):
    name = "add"
    description = "Add two integers"

    def run(self, a: int, b: int = 1) -> int:
        return a + b


tool = Add()
assert tool.execute(a=2, b=3) == 5
print(tool.schema.parameters)
```

Tool schemas are provider-neutral JSON Schema. Tool names are 1–64 letters, digits,
underscores, or hyphens. Descriptions must be nonempty. Named parameters are required;
variadic/positional-only signatures require an explicit input model.

For constraints, declare a Pydantic model:

```python
from pydantic import BaseModel, Field
from harness.tools import Tool


class Inputs(BaseModel):
    value: int = Field(gt=0)


class Double(Tool):
    name = "double"
    description = "Double a positive integer"
    input_model = Inputs

    def run(self, value: int) -> int:
        return value * 2


assert Double().execute(value=3) == 6
```

Inputs are validated strictly; unknown keys are rejected even if the input model
would otherwise ignore extras. `execute()` wraps implementation exceptions in ToolError.
Calling `run()` directly bypasses input validation. Outputs must be text or JSON values.
The Agent bounds serialized output before appending it to context; file reads and shell
capture also have their own bounds.

Built-ins:

| Tool | Inputs | Behavior |
| --- | --- | --- |
| ReadFile | path | UTF-8 file, default maximum 1,000,000 bytes |
| WriteFile | path, content | Create parents, replace UTF-8 contents, report bytes written |
| ListFiles | path="." | Sorted immediate entries, maximum 1,000 entries |
| Shell | command: string or list of strings | stdout/stderr, exit_code, timeout, truncated |

Directory labels end with `/`, symlink labels with `@`. ListFiles is not recursive.
Give a workspace directly or let Agent bind built-ins to its workspace:

```python
from harness.tools import ReadFile, Shell

reader = ReadFile(workspace=".", max_bytes=100_000)
shell = Shell(cwd=".", timeout=30, max_output_length=10_000)
result = shell.execute(command=["python", "--version"])
print(result["stdout"], result["exit_code"])
```

Prefer argument lists; they preserve Windows paths and quoting. String commands use
shlex parsing with platform-specific quoting and do not implicitly expand shell operators.
For pipes or redirection, explicitly invoke an interpreter such as
`["sh", "-c", "command | other"]` or `["powershell", "-NoProfile", "-Command", "..."]`.
Shell output is bounded across stdout and stderr in bytes before UTF-8 decoding.
Timeout handling attempts to terminate descendants; detached/background processes
can outlive the parent, so use OS isolation when resource containment matters.

Custom tools are arbitrary trusted Python code. Agent workspace binding applies only
to built-in tools; implement appropriate controls in custom tools. See [security](security.md).
