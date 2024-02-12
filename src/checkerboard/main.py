"""Application definition for Checkerboard."""

__all__ = ["create_app"]
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

import redis.asyncio as redis
from fastapi import FastAPI
from safir.fastapi import ClientRequestError, client_request_error_handler
from safir.logging import configure_uvicorn_logging
from slack_sdk.http_retry.builtin_async_handlers import (
    AsyncRateLimitErrorRetryHandler,
)
from slack_sdk.web.async_client import AsyncWebClient

from .config import Configuration
from .dependencies.config import config_dependency
from .dependencies.context import context_dependency
from .handlers import ei_router, ii_router, m_router


def create_app(
    *,
    config: Configuration | None = None,
    slack: AsyncWebClient | None = None,
    redis_client: redis.Redis | None = None,
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
    slack : `AsyncWebClient`, optional
        The Slack AsyncWebClient to use.  If not provided, one will be created
        based on the application configuration.  This is a parameter primarily
        to allow for dependency injection by the test suite.
    redis_client : `redis.asyncio.Redis`, optional
        The Redis async client to use.  If not provided, one will be created
        based on the application configuration.  This is a parameter primarily
        to allow for dependency injection by the test suite.
    """
    if not config:
        config = config_dependency.config()
    if not slack:
        slack = AsyncWebClient(config.slack_token)
        slack.retry_handlers.append(
            AsyncRateLimitErrorRetryHandler(max_retry_count=5)
        )
    if not redis_client:
        redis_client = redis.Redis.from_url(
            config.redis_url,
            password=config.redis_password,
            socket_timeout=5,
            auto_close_connection_pool=True,
        )

    @asynccontextmanager
    async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
        await context_dependency.initialize(config, slack, redis_client)

        # Now we're going to wait for the mapper to populate.  This will
        # take 20 minutes or so if there is no redis cache.  However, if
        # there is a redis cache, we'll start the app with what we have
        # and refresh in the background.
        pcontext = context_dependency.get_process_context()
        await pcontext.mapper.start()

        # Having gotten our initial map, we now kick off the background
        # refresh task.
        await pcontext.create_mapper_refresh_task()

        # And with that running, we can yield the app back to the lifecycle
        # manager.

        yield
        await context_dependency.aclose()

    path_prefix = f"/{config_dependency.config().name}"
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
        openapi_url=f"{path_prefix}/openapi.json",
        docs_url=f"{path_prefix}/docs",
        redoc_url=f"{path_prefix}/redoc",
        lifespan=_lifespan,
    )

    # Add our routes
    # Internal routes
    app.include_router(ii_router)
    # External routes
    app.include_router(ei_router, prefix=path_prefix)
    app.include_router(m_router, prefix=path_prefix)

    # Add exception handlers
    app.exception_handler(ClientRequestError)(client_request_error_handler)

    # Rationalize logs
    configure_uvicorn_logging(config.log_level)

    return app