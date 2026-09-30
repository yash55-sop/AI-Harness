"""Install the built wheel in a temporary venv, then run outside the source tree."""

import os
import subprocess
import tempfile
import venv
from pathlib import Path

SMOKE = """
from pathlib import Path
import harness
from harness import Agent, CodingAgent
from harness.models import ModelResponse, ToolCall, Usage
from harness.providers import BaseProvider

assert "site-packages" in str(Path(harness.__file__)).lower()
assert Path(harness.__file__).with_name("py.typed").is_file()

class Fake(BaseProvider):
    def __init__(self, responses):
        self.responses = iter(responses)
    def generate(self, messages, tools=None):
        return next(self.responses)

with Agent("fake/model", provider=Fake([ModelResponse(text="installed")])) as agent:
    assert agent.run("hello") == "installed"

workspace = Path("project")
workspace.mkdir()
(workspace / "sample.py").write_text("value = 1\\n", encoding="utf-8")
provider = Fake([
    ModelResponse(tool_calls=[ToolCall("read", "read_file", {"path": "sample.py"})]),
    ModelResponse(tool_calls=[ToolCall("write", "write_file", {
        "path": "sample.py", "content": "value = 2\\n"})]),
    ModelResponse(text="done", usage=Usage(3, 1)),
])
with CodingAgent("fake/model", workspace, provider=provider, enable_shell=False) as agent:
    assert agent.run("fix sample") == "done"
    assert agent.last_result.steps == 3
assert (workspace / "sample.py").read_text() == "value = 2\\n"
print("Installed wheel: Agent and CodingAgent smoke checks passed")
"""


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    wheels = list((root / "dist").glob("*.whl"))
    if len(wheels) != 1:
        raise SystemExit("Expected exactly one wheel in dist; build into a clean dist directory")
    with tempfile.TemporaryDirectory(prefix="harness-wheel-") as temporary:
        work = Path(temporary)
        environment = work / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        scripts = environment / ("Scripts" if os.name == "nt" else "bin")
        python = scripts / ("python.exe" if os.name == "nt" else "python")
        subprocess.run(
            [str(python), "-m", "pip", "install", f"{wheels[0]}[openai]"], check=True, cwd=work
        )
        subprocess.run([str(python), "-m", "pip", "check"], check=True, cwd=work)
        subprocess.run([str(python), "-I", "-c", SMOKE], check=True, cwd=work)
        subprocess.run([str(python), "-I", "-m", "harness", "--version"], check=True, cwd=work)
        command = scripts / ("harness.exe" if os.name == "nt" else "harness")
        subprocess.run([str(command), "--help"], check=True, cwd=work, stdout=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
