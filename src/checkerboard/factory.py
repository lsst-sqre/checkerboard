"""Create Checkerboard components."""

import asyncio
import time
from collections.abc import AsyncIterator
from contextlib import aclosing, asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Self

from safir.logging import configure_logging
from slack_sdk.web.async_client import AsyncWebClient
from structlog import get_logger
from structlog.stdlib import BoundLogger

from .config import Configuration
from .storage.slack import SlackGitHubMapper


@dataclass
class ProcessContext:
    """Per-process application context.

    This object caches all of the per-process singletons that can be
    shared across requests.  That's basically just the configuration,
    the name mapping, and the task to do periodic refresh of the
    mapping.


    Parameters
    ----------
    config
        Checkerboard configuration.
    slack
        Configured Slack AsyncWebClient (optional).  If set, the
        AsyncWebClient must already have the authentication token set.
        If not, the AsyncWebClient will be created from the auth token in
        the configuration.
    """

    config: Configuration
    """Checkerboard configuration."""

    client: AsyncWebClient
    """Slack Client."""

    mapper: SlackGitHubMapper
    """Object holding map between Slack users and GitHub accounts."""

    refresh_task: asyncio.Task | None = None
    """Task to periodically refresh user map."""

    @classmethod
    async def from_config(
        cls, config: Configuration, slack: AsyncWebClient | None = None
    ) -> Self:
        """Create a new process context from Checkerboard configuration."""
        configure_logging(
            profile=config.profile,
            log_level=config.log_level,
            name=config.logger_name,
        )
        if slack is None:
            slack = AsyncWebClient(config.slack_token)
        mapper = SlackGitHubMapper(
            slack=slack,
            profile_field_name=config.profile_field,
            logger=get_logger(config.logger_name),
        )
        return cls(config=config, mapper=mapper, client=slack)

    async def aclose(self) -> None:
        """Clean up a process context.

        Called during shutdown, or before recreating the process context
        using a different configuration.
        """
        if self.refresh_task is not None:
            self.refresh_task.cancel()
            with suppress(asyncio.CancelledError):
                await self.refresh_task

    async def create_mapper_refresh_task(self) -> None:
        """Spawn a background task to refresh the Slack <-> GitHub mapper."""
        self.refresh_task = asyncio.create_task(
            self._mapper_periodic_refresh()
        )

    async def _mapper_periodic_refresh(self) -> None:
        """Refresh the Slack <-> GitHub identity mapper.

        This runs as an infinite loop and is meant to be spawned as an
        asyncio Task and cancelled when the application is shut down.
        """
        interval = self.config.refresh_interval
        await asyncio.sleep(interval)
        # We sleep above because we run (and wait for) the refresh at
        # creation time.  We assume you're going to kick off the task
        # immediately upon startup, which will happen immediately
        # after the first map-build finishes.
        while True:
            start = time.time()
            await self.mapper.refresh()
            now = time.time()
            if start + interval > now:
                await asyncio.sleep(interval - (now - start))


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
        cls, config: Configuration, slack: AsyncWebClient | None
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
        slack
            Configured Slack AsyncWebClient (optional).  If set, the
            AsyncWebClient must already have the authentication token set.

        Returns
        -------
        Factory
            Newly-created factory.  The caller must call `aclose` on the
            returned object during shutdown.
        """
        context = await ProcessContext.from_config(config, slack)
        logger = get_logger("checkerboard")
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
