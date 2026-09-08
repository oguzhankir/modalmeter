"""Thin command-line entry point; feature commands arrive in later milestones."""

from typing import Annotated

import typer

from modalmeter import __version__

app = typer.Typer(
    help="ModalMeter: multimodal profiling foundations. Inspection is not implemented yet.",
    add_completion=False,
    invoke_without_command=True,
)


def _version(value: bool) -> None:
    if value:
        typer.echo(f"modalmeter {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_version, is_eager=True, help="Show the version and exit."
        ),
    ] = False,
) -> None:
    """Show the implemented command surface."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
