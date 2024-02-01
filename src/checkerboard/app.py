"""The main application definition for checkerboard service."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp.web import Application
from aiohttp_basicauth_middleware import basic_auth_middleware
from fastapi import FastAPI
from safir.logging import configure_logging
from safir.metadata import setup_metadata
from safir.middleware import bind_logger
from slack import WebClient

from checkerboard.config import Configuration
from checkerboard.handlers import init_external_routes, init_internal_routes

__all__ = ["create_app"]


if TYPE_CHECKING:
    from typing import Optional


async def create_app(
    *,
    config: Optional[Configuration] = None,
    slack: Optional[WebClient] = None,
) -> FastAPI:
    """Create and configure the Checkerboard application.

    On startup, Checkerboard will rebuild its mapping of Slack users to GitHub
    users and will not start responding to routes (including health checks)
    until that is done.  This will take 10-15 minutes, so set health check
    timeouts accordingly.

    Parameters
    ----------
    config : `Configuration`, optional
        The configuration to use.  If not provided, the default Configuration
        will be used.  This is a parameter primarily to allow for dependency
        injection by the test suite.
    slack : `WebClient`, optional
        The Slack WebClient to use.  If not provided, one will be created
        based on the application configuration.  This is a parameter primarily
        to allow for dependency injection by the test suite.
    """
    if not config:
        config = Configuration()
    configure_logging(
        profile=config.profile,
        log_level=config.log_level,
        name=config.logger_name,
    )

    # Create the Slack to GitHub mapper and retrieve the initial mapping
    # before creating the application.  This ensures that it will not respond
    # to health checks until the mapping is ready.
    if not slack:
        slack = WebClient(config.slack_token, run_async=True)
    mapper = await create_mapper(config, slack)

    root_app = Application()
    root_app["safir/config"] = config
    root_app["checkerboard/mapper"] = mapper
    setup_metadata(package_name="checkerboard", app=root_app)
    setup_middleware(root_app)
    root_app.add_routes(init_internal_routes())
    root_app.cleanup_ctx.append(create_mapper_refresh_task)

    sub_app = Application()
    setup_middleware(sub_app)
    sub_app.add_routes(init_external_routes())
    root_app.add_subapp(f"/{config.name}", sub_app)

    # The basic auth middleware requires the full URL, so attach it to the
    # root app, even though all the protected URLs are in the sub app.
    root_app.middlewares.append(
        basic_auth_middleware(
            (f"/{config.name}/slack", f"/{config.name}/github"),
            {config.username: config.password},
        )
    )

    return root_app


def setup_middleware(app: Application) -> None:
    """Add middleware to the application."""
    app.middlewares.append(bind_logger)
