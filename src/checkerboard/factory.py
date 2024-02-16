"""Create Checkerboard components."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import aclosing, asynccontextmanager, suppress
from typing import Self

import redis.asyncio as redis
import structlog
from safir.logging import configure_logging
from slack_sdk.http_retry.builtin_async_handlers import (
    AsyncRateLimitErrorRetryHandler,
)
from slack_sdk.web.async_client import AsyncWebClient
from structlog import get_logger
from structlog.stdlib import BoundLogger

from .config import Configuration
from .service.mapper import Mapper
from .storage.redis import MappingCache
from .storage.slack import SlackGitHubMapper


class ProcessContext:
    """Per-process application context.

    This object caches all of the per-process singletons that can be
    shared across requests.  That's basically the configuration, the
    slack-to-github storage object, the redis storage object, and a task
    to hold the periodic refresh loop.
    """

    def __init__(
        self,
        config: Configuration,
        slack_client: AsyncWebClient | None,
        redis_client: redis.Redis | None,
        *,
        logger: BoundLogger | None = None,
    ) -> None:
        """
        Parameters
        ----------
        config : `checkerboard.Configuration`
            Checkerboard configuration.
        slack_client : `slack_sdk.web.async_client.AsyncWebClient` | None
            Configured Slack AsyncWebClient (optional).  If set, the
            AsyncWebClient must already have the authentication token set.
            If not, the AsyncWebClient will be created from the auth token in
            the configuration.
        redis_client : `redis.asyncio.Redis` | None
            Configured Redis async client (optional).  If not set, the redis
            client will be created from the redis url and password in the
            configuration.
        logger : `BoundLogger` | None
            Logger object.  If not set, it will be initialized from the
            configuration.
        """
        print(f"*** {logger} ***")  # noqa: T201
        if logger is None:
            configure_logging(
                profile=config.profile,
                log_level=config.log_level,
                name=config.logger_name,
            )
            logger = structlog.get_logger(config.logger_name)
        if slack_client is None:
            # Increase the timeout, because rate-limit retries are
            # fairly frequent
            slack_client = AsyncWebClient(config.slack_token, timeout=60)
        slack_client.retry_handlers.append(
            AsyncRateLimitErrorRetryHandler(max_retry_count=5)
        )
        if redis_client is None:
            redis_client = redis.Redis.from_url(
                config.redis_url,
                password=config.redis_password,
                socket_timeout=5,
                auto_close_connection_pool=True,
            )
        self.config = config
        self.redis = MappingCache(redis_client=redis_client, logger=logger)
        self.slack = SlackGitHubMapper(
            slack_client=slack_client,
            redis=self.redis,
            profile_field_name=config.profile_field,
            logger=logger,
        )
        self.mapper = Mapper(slack=self.slack, redis=self.redis, logger=logger)
        self.refresh_task: asyncio.Task | None = None

    @classmethod
    async def from_config(
        cls,
        config: Configuration,
        slack_client: AsyncWebClient | None,
        redis_client: redis.Redis | None,
        *,
        logger: BoundLogger | None = None,
    ) -> Self:
        """Create a new process context from Checkerboard configuration.

        This is an async classmethod.
        """
        return cls(config, slack_client, redis_client, logger=logger)

    async def aclose(self) -> None:
        """Clean up a process context.

        Called during shutdown, or before recreating the process context
        using a different configuration.
        """
        if self.refresh_task is not None:
            self.refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.refresh_task
        await self.redis.aclose()

    async def create_mapper_refresh_task(self) -> None:
        """Spawn a background task to refresh the Slack <-> GitHub mapper."""
        self.refresh_task = asyncio.create_task(
            self.mapper.periodic_refresh(interval=self.config.refresh_interval)
        )


class Factory:
    """Build Checkerboard components.

    Parameters
    ----------
    context
        Shared process context.
    logger
        Logger to use for errors.
    """

    @classmethod
    async def create(
        cls,
        config: Configuration,
        slack_client: AsyncWebClient | None = None,
        redis_client: redis.Redis | None = None,
    ) -> Self:
        """Create a component factory outside of a request.

        Intended for long-running daemons other than the FastAPI web
        application.  This class method should only be used in situations
        where an async context manager cannot be used.  Do not use this
        factory inside the web application or anywhere that may use the
        default `Factory`.

        If an async context manager can be used, call `standalone` rather
        than this method.

        Parameters
        ----------
        config
            Checkerboard configuration.
        slack_client
            Configured Slack AsyncWebClient (optional).  If set, the
            AsyncWebClient must already have the authentication token set.
        redis_client
            Configured Redis asyncio client (optional).

        Returns
        -------
        Factory
            Newly-created factory.  The caller must call `aclose` on the
            returned object during shutdown.
        """
        context = await ProcessContext.from_config(
            config=config, slack_client=slack_client, redis_client=redis_client
        )
        logger = get_logger(
            "checkerboard",
            profile=config.profile,
            log_level=config.log_level,
        )
        return cls(context, logger)

    @classmethod
    @asynccontextmanager
    async def standalone(
        cls, config: Configuration, slack: AsyncWebClient | None = None
    ) -> AsyncIterator[Self]:
        """Async context manager for Checkerboard components.

        Intended for background jobs.  Uses the non-request default values for
        the dependencies fo `Factory`.  Do not use this factory inside the
        web application or anywhere that may use the default `Factory`.

        Parameters
        ----------
        config
            Checkerboard configuration.
        slack
            Configured Slack AsyncWebClient (optional).  If set, the
            AsyncWebClient must already have the authentication token set.

        Yields
        ------
        Factory
          The factory.  Must be used as an async context manager.
        """
        factory = await cls.create(config, slack)
        async with aclosing(factory):
            yield factory

    def __init__(self, context: ProcessContext, logger: BoundLogger) -> None:
        self._context = context
        self._logger = logger

    def set_logger(self, logger: BoundLogger) -> None:
        """Replace the internal logger.

        Used by the context dependency to update the logger for all
        newly-created components when it's rebound with additional context.

        Parameters
        ----------
        logger
            New logger.
        """
        self._logger = logger

    async def aclose(self) -> None:
        """Shut down the factory.

        After this method is called, the factory object is no longer valid and
        must not be used.
        """
        await self._context.aclose()
