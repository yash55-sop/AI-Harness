"""A small Typer interface to CodingAgent."""

from pathlib import Path
from typing import Annotated

import typer

from harness import Agent, CodingAgent, HarnessError, __version__
from harness.tools import ListFiles, ReadFile

app = typer.Typer(add_completion=False, pretty_exceptions_enable=False)


def version_callback(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def main(
    task: Annotated[str, typer.Argument(help="Task for the agent.")],
    model: Annotated[
        str, typer.Option(envvar="HARNESS_MODEL", help="Provider/model-name.")
    ] = "openai/gpt-4.1-mini",
    workspace: Annotated[Path, typer.Option(help="Existing working directory.")] = Path("."),
    max_steps: Annotated[int | None, typer.Option(min=1, help="Maximum model calls.")] = None,
    verbose: Annotated[bool, typer.Option("--verbose", help="Print progress to stderr.")] = False,
    read_only: Annotated[
        bool, typer.Option("--read-only", help="Only enable read_file and list_files.")
    ] = False,
    no_shell: Annotated[bool, typer.Option("--no-shell", help="Disable shell execution.")] = False,
    temperature: Annotated[
        float | None,
        typer.Option(
            min=0, max=2, help="Sampling temperature; omitted by default for model compatibility."
        ),
    ] = None,
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=version_callback, is_eager=True, help="Show version and exit."
        ),
    ] = False,
) -> None:
    """Run a coding task. By default, grants file writes and command execution."""
    try:
        if read_only:
            agent: Agent = Agent(
                model,
                workspace=workspace,
                tools=[ReadFile(workspace), ListFiles(workspace)],
                max_steps=max_steps,
                verbose=verbose,
                temperature=temperature,
            )
        else:
            agent = CodingAgent(
                model,
                workspace=workspace,
                enable_shell=not no_shell,
                max_steps=max_steps,
                verbose=verbose,
                temperature=temperature,
            )
        with agent:
            typer.echo(agent.run(task))
    except HarnessError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from None
