from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml
from pydantic import ValidationError
from rich.console import Console

from agentarena_local.config import init_workspace
from agentarena_local.tasks import TaskConfig, load_task

app = typer.Typer(
    name="agentarena",
    help="AgentArena Local: evaluate AI coding agents in local Git repositories.",
    no_args_is_help=True,
)
console = Console()


def _format_validation_error(exc: ValidationError) -> str:
    lines: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"])
        message = error["msg"]
        input_value = error.get("input")
        lines.append(f"- {location}: {message} (input: {input_value!r})")
    return "\n".join(lines)


@app.command()
def init(
    path: Annotated[
        Path,
        typer.Argument(
            help="Repository or workspace path to initialize for AgentArena Local.",
        ),
    ] = Path("."),
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="Overwrite existing AgentArena config."),
    ] = False,
) -> None:
    """Create the local AgentArena configuration directory."""
    try:
        result = init_workspace(path, force=force)
    except FileExistsError as exc:
        console.print(f"[red]Error:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    action = "Updated" if result.overwritten else "Created"
    console.print(f"[green]{action}[/green] AgentArena workspace at {result.config_dir}")


@app.command()
def validate(
    task_file: Annotated[
        Path,
        typer.Argument(
            exists=True,
            file_okay=True,
            dir_okay=False,
            readable=True,
            help="Path to task.yaml.",
        ),
    ],
) -> None:
    """Validate a task.yaml file."""
    try:
        task = load_task(task_file)
    except ValidationError as exc:
        console.print(f"[red]Invalid task:[/red] {task_file}")
        console.print(_format_validation_error(exc))
        raise typer.Exit(code=1) from exc
    except (ValueError, yaml.YAMLError) as exc:
        console.print(f"[red]Invalid task:[/red] {task_file}")
        console.print(str(exc))
        raise typer.Exit(code=1) from exc

    console.print(f"[green]Valid task[/green]: {task.id} ({task.type})")


@app.command()
def schema() -> None:
    """Print the JSON schema for task.yaml."""
    console.print_json(data=TaskConfig.model_json_schema())
