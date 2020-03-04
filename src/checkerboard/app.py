"""The main application definition for checkerboard service."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING

from aiohttp.web import Application
from aiohttp_basicauth_middleware import basic_auth_middleware
from safir.logging import configure_logging
from safir.metadata import setup_metadata
from safir.middleware import bind_logger
from slack import WebClient

from checkerboard.config import Configuration
from checkerboard.handlers import init_external_routes, init_internal_routes
from checkerboard.slack import SlackGitHubMapper

__all__ = ["create_app"]


if TYPE_CHECKING:
    from typing import AsyncIterator, Optional


async def create_app(slack: Optional[WebClient] = None) -> Application:
    """Create and configure the Checkerboard application.

    On startup, Checkerboard will rebuild its mapping of Slack users to GitHub
    users and will not start responding to routes (including health checks)
    until that is done.  This will take 10-15 minutes, so set health check
    timeouts accordingly.

    Parameters
    ----------
    slack : `WebClient`, optional
        The Slack WebClient to use.  If not provided, one will be created
        based on the application configuration.  This is a parameter primarily
        to allow for dependency injection by the test suite.
    """
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
    root_app.add_subapp(f'/{root_app["safir/config"].name}', sub_app)

    # The basic auth middleware requires the full URL, so attach it to the
    # root app, even though all the protected URLs are in the sub app.
    root_app.middlewares.append(
        basic_auth_middleware(
            ("/checkerboard/slack", "/checkerboard/github"),
            {config.username: config.password},
        )
    )

    return root_app


async def create_mapper(
    config: Configuration, slack: WebClient
) -> SlackGitHubMapper:
    """Create the Slack <-> GitHub identity mapper.

    Does not return until the mapper has initialized its mapping tables (which
    takes about 10-15 minutes).

    Parameters
    ----------
    config : `Configuration`
        The Checkerboard application configuration.
    """
    mapper = SlackGitHubMapper(slack, config.profile_field)
    await mapper.refresh()

    return mapper


async def create_mapper_refresh_task(app: Application) -> AsyncIterator[None]:
    """Spawn a background task to refresh the Slack <-> GitHub mapper.

    Run this as an aiohttp cleanup context so that it will be shut down
    automatically when the application is shut down.

    Parameters
    ----------
    app : `Application`
        The Checkerboard root application.
    """
    config = app["safir/config"]
    mapper = app["checkerboard/mapper"]
    task = asyncio.create_task(mapper_refresh(mapper, config.refresh_interval))

    yield

    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


async def mapper_refresh(mapper: SlackGitHubMapper, interval: int) -> None:
    """Refresh the Slack <-> GitHub identity mapper.

    This runs as an infinite loop and is meant to be spawned as an asyncio
    Task and cancelled when the application is shut down.

    Parameters
    ----------
    mapper : `SlackGitHubMapper`
        The Slack <-> GitHub identity mapper to refresh.
    interval : `int`
        The interval between refreshes in seconds.  This is not the sleep
        time; it is the time between kicking off new refresh jobs.  If it is
        smaller than the length of time a single refresh takes, Checkerboard
        will refresh continuously.
    """
    await asyncio.sleep(interval)
    while True:
        start = time.time()
        await mapper.refresh()
        now = time.time()
        if start + interval > now:
            await asyncio.sleep(interval - (now - start))


def setup_middleware(app: Application) -> None:
    """Add middleware to the application."""
    app.middlewares.append(bind_logger)
