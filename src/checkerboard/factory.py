"""Create Checkerboard components."""

import asyncio
from dataclasses import dataclass

from safir.logging import configure_logging
from slack import WebClient
from structlog import get_logger
from structlog.stdlib import BoundLogger

from checkerboard.slack import SlackGitHubMapper


async def _mapper_refresh(mapper: SlackGitHubMapper, interval: int) -> None:
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


@dataclass(frozen=True, slots=True)
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
        Configured Slack WebClient (optional).  If set, the WebClient
        must already have the authentication token set and have been
        created with ``run_async`` set.
    """

    config: Configuration
    """Checkerboard configuration."""

    mapper: SlackGitHubMapper
    """Object holding map between Slack users and GitHub accounts."""

    refresh_task: AsyncIterator[None] | None = None
    """Task to periodically refresh user map."""

    @classmethod
    async def from_config(
        cls, config: Configuration, slack: WebClient | None = None
    ) -> Self:
        """Create a new process context from Checkerboard configuration."""
        configure_logging(
            profile=config.profile,
            log_level=config.log_level,
            name=config.logger_name,
        )
        if slack is None:
            slack = WebClient(config.slack_token, run_async=True)
        mapper = SlackGitHubMapper(
            slack=slack,
            profile_field_name=config.profile_field,
            logger=get_logger(config.logger_name),
        )
        return cls(config=config, mapper=mapper)

    async def aclose(self) -> None:
        """Clean up a process context.

        Called during shutdown, or before recreating the process context
        using a different configuration.
        """
        if self.refresh_task is not None:
            self.refresh_task.cancel()
            try:
                await self.refresh_task
            except asyncio.CancelledError:
                pass
            self.refresh_task = None

    async def create_mapper_refresh_task(self) -> None:
        """Spawn a background task to refresh the Slack <-> GitHub mapper."""
        logger = get_logger(self.config.logger_name)
        if self.mapper is None:
            logger.warning("No mapper is defined; cannot create refresh task.")
            return
        self.refresh_task = asyncio.create_task(
            _mapper_refresh(mapper, config.refresh_interval)
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
        cls, config: Configuration, slack: WebClient | None
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
            Configured Slack WebClient (optional).  If set, the WebClient
            must already have the authentication token set and have been
            created with ``run_async`` set.

        Returns
        -------
        Factory
            Newly-created factory.  The caller must call `aclose` on the
            returned object during shutdown.
        """
        context = await ProcessContext.from_config(config, slack)
        logger = structlog.get_logger("checkerboard")
        return cls(context, logger)

    @classmethod
    @asynccontextmanager
    async def standalone(
        cls, config: Configuration, slack: WebClient | None = None
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
            Configured Slack WebClient (optional).  If set, the WebClient
            must already have the authentication token set and have been
            created with ``run_async`` set.

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

    async def aclose(self) -> None:
        """Shut down the factory.

        After this method is called, the factory object is no longer valid and
        must not be used.
        """
        await self._context.aclose()
