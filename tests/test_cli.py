"""CLI arguments, output, capabilities and useful errors without paid calls."""

from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from harness import Agent, CodingAgent, __version__
from harness.cli import main as cli
from harness.models import ModelResponse
from tests.fakes import FakeProvider

runner = CliRunner()


@pytest.mark.parametrize("flags", [[], ["--no-shell"], ["--read-only"]])
def test_cli_capabilities_and_options(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flags: list[str],
) -> None:
    agents = []

    def plain(*args: Any, **kwargs: Any) -> Agent:
        agent = Agent(*args, **kwargs, provider=FakeProvider(ModelResponse(text="done")))
        agents.append(agent)
        return agent

    def coding(*args: Any, **kwargs: Any) -> CodingAgent:
        agent = CodingAgent(*args, **kwargs, provider=FakeProvider(ModelResponse(text="done")))
        agents.append(agent)
        return agent

    monkeypatch.setattr(cli, "Agent", plain)
    monkeypatch.setattr(cli, "CodingAgent", coding)
    result = runner.invoke(
        cli.app,
        [
            "--model",
            "fake/model",
            "--workspace",
            str(tmp_path),
            "--max-steps",
            "3",
            *flags,
            "Explain this project",
        ],
    )
    assert result.exit_code == 0, result.output
    assert result.stdout.strip() == "done"
    names = {schema.name for schema in agents[0]._registry.schemas}
    assert agents[0].config.max_steps == 3
    if "--read-only" in flags:
        assert names == {"read_file", "list_files"}
    elif "--no-shell" in flags:
        assert names == {"read_file", "write_file", "list_files"}
    else:
        assert "shell" in names


def test_missing_credentials_is_a_clean_error(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["--workspace", str(tmp_path), "hi"])
    assert result.exit_code == 1
    assert "OPENAI_API_KEY" in result.stderr
    assert "Traceback" not in result.output


def test_invalid_workspace(tmp_path: Path) -> None:
    result = runner.invoke(cli.app, ["--workspace", str(tmp_path / "missing"), "hi"])
    assert result.exit_code == 1
    assert "existing directory" in result.output


def test_help_version_and_invalid_limit() -> None:
    assert runner.invoke(cli.app, ["--help"]).exit_code == 0
    result = runner.invoke(cli.app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
    assert runner.invoke(cli.app, ["--max-steps", "0", "hello"]).exit_code == 2


def test_model_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    received = []

    def factory(model: str, **kwargs: Any) -> Agent:
        received.append(model)
        return Agent(
            model,
            provider=FakeProvider(),
            **{key: value for key, value in kwargs.items() if key != "enable_shell"},
        )

    monkeypatch.setattr(cli, "CodingAgent", factory)
    monkeypatch.setenv("HARNESS_MODEL", "fake/environment")
    result = runner.invoke(cli.app, ["--workspace", str(tmp_path), "hi"])
    assert result.exit_code == 0
    assert received == ["fake/environment"]
