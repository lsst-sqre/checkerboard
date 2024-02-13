"""Administrative command-line interface."""

__all__ = ["main", "help", "run"]


import click
import uvicorn
from safir.click import display_help


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(message="%(version)s")
def main() -> None:
    """Administrative command-line interface for checkerboard."""


@main.command()
@click.argument("topic", default=None, required=False, nargs=1)
@click.argument("subtopic", default=None, required=False, nargs=1)
@click.pass_context
def help(ctx: click.Context, topic: str | None, subtopic: str | None) -> None:
    """Show help for any command."""
    display_help(main, ctx, topic, subtopic)


@main.command()
@click.option(
    "--port", default=8080, type=int, help="Port to run the application on."
)
def run(port: int) -> None:
    """Run the application (for production)."""
    uvicorn.run(
        "checkerboard.main:create_app",
        factory=True,
        port=port,
        reload=True,
        reload_dirs=["src"],
    )
