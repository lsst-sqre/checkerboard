"""Application definition for Checkerboard."""

__all__ = ["create_app"]
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from safir.logging import configure_uvicorn_logging
from slack import WebClient  # type: ignore[attr-defined]

from checkerboard.config import Configuration
from checkerboard.dependencies.config import config_dependency
from checkerboard.dependencies.context import context_dependency
from checkerboard.handlers import internal_routes, routes


async def create_app(
    *,
    config: Configuration | None = None,
    slack: WebClient | None = None,
) -> FastAPI:
    """Create and configure the Checkerboard FastAPI application.

    This is in a function rather than using a global variable (as is more
    typical for FastAPI) because that's the usual SQuaRE pattern.  In this
    particular case we don't need to have fancy middleware-dependent-on-
    configuration or anything, but we'll keep it this way for consistency.

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
        config = config_dependency.config()
    if not slack:
        slack = WebClient(config.slack_token, run_async=True)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await context_dependency.initialize(config, slack)

        # Now we're going to wait for the mapper to populate.  This may
        # take 10-15 minutes, so adjust healthchecks appropriately.
        #
        # TODO @athornton: Add Redis to the deployment to cache the mapper,
        # so we can restart without having to wait.
        await context_dependency.process_context.mapper.refresh()

        # Having gotten our initial map, we now kick off the background
        # refresh task.
        await context_dependency.process_context.create_mapper_refresh_task()

        # And with that running, we can yield the app back to the lifecycle
        # manager.

        yield

        await context_dependency.aclose()

    app = FastAPI(
        title="Checkerboard",
        description=(
            "Checkerboard is a FastAPI application for tracking the mapping"
            " between GitHub accounts and Slack usernames."
        ),
        version=version("checkerboard"),
        tags_metadata=[
            {
                "name": "internal",
                "description": (
                    "Internal routes used by the ingress and health checks."
                ),
            },
        ],
        openapi_url="/auth/openapi.json",
        docs_url="/auth/docs",
        redoc_url="/auth/redoc",
        lifespan=lifespan,
    )

    # Add our routes
    app.include_router(internal_routes)
    app.include_router(routes)

    configure_uvicorn_logging(config.log_level)

    return app
