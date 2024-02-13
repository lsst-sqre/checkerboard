"""The mapper service implements interaction with a user map, which is
backed by redis and refreshed periodically from GitHub.
"""
import asyncio
import logging
import time
from dataclasses import dataclass, field

from ..storage.redis import MappingCache
from ..storage.slack import SlackGitHubMapper


@dataclass
class UserMap:
    """Holds the Slack->GitHub map and its inverse."""

    slack_to_github: dict[str, str] = field(default_factory=dict)
    github_to_slack: dict[str, str] = field(default_factory=dict)


class Mapper:
    """Provides the interaction layer that our routes will use."""

    def __init__(
        self,
        slack: SlackGitHubMapper,
        redis: MappingCache,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._slack = slack
        self._redis = redis
        self._logger = logger or logging.getLogger(__name__)
        self._map = UserMap()
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        """Run this on startup.

        First it will get a map from the redis client.  If that has
        data in it, will use that.  If not, it will block until the
        slack client has run a refresh, which will presumably populate
        the cache, which will then be propagated to the map in redis.

        The intent is to allow us to start quickly and offer service, while
        the background map refresh tracks user changes.
        """
        if self._map.slack_to_github:
            self._logger.warning(
                "Non-empty user map exists; returning from start() as it's"
                " obviously post-startup"
            )
            return
        slack_to_github = await self._redis.get_all()
        if not slack_to_github:
            self._logger.warning(
                "Redis cache is empty.  Refreshing from Slack/Github."
            )
            # Redis cache is empty.  We need a refresh.
            await self._slack.refresh()
        await self.refresh()

    async def refresh(self) -> None:
        """Refresh the in-memory map from Redis."""
        slack_to_github = await self._redis.get_all()
        if not slack_to_github:
            self._logger.warning("No user mapping found in redis")

        github_to_slack: dict[str, str] = {}
        for key in slack_to_github:
            value = slack_to_github[key]
            github_to_slack[value] = key

        async with self._lock:
            self._map.slack_to_github = slack_to_github
            self._map.github_to_slack = github_to_slack

    async def map(self) -> dict[str, str]:
        """Return the entire Slack-to-GitHub map.

        Returns
        -------
        map: dict[str,str]
            The map of Slack users to GitHub users.  Each key is a user's
            Slack ID (not the display name or the real name), and the value
            is the corresponding GitHub username.
        """
        async with self._lock:
            return self._map.slack_to_github

    async def slack_for_github_user(self, github_id: str) -> str:
        """Return the Slack user ID for a GitHub user, if any.

        If the Slack

        Parameters
        ----------
        github_id : `str`
            A GitHub username (not case-sensitive).

        Returns
        -------
        slack : `str`
            The corresponding Slack user ID (not the display name or real
            name), or the empty string if no Slack users have that GitHub
            user set in their profile.
        """
        async with self._lock:
            return self._map.github_to_slack.get(github_id.lower(), "")

    async def github_for_slack_user(self, slack_id: str) -> str:
        """Return the GitHub user for a Slack user ID, if any.

        Parameters
        ----------
        slack_id : `str`
            The Slack user ID (not the display name or real name).

        Returns
        -------
        github_id : `str`
            The corresponding GitHub username coerced to lowercase, or the
            empty string if that Slack user does not exist or does not
            have a GitHub user set in their profile.
        """
        async with self._lock:
            return self._map.slack_to_github.get(slack_id, "")

    async def periodic_refresh(self, interval: int = 3600) -> None:
        """Refresh the Slack <-> GitHub identity mapper.

        This runs as an infinite loop and is meant to be spawned as an
        asyncio Task and cancelled when the application is shut down.
        """
        while True:
            start = time.time()
            self._logger.debug(f"Running periodic refresh (each {interval} s)")
            changed = await self._slack.refresh()
            if changed:
                await self.refresh()
            now = time.time()
            elapsed = now - start
            self._logger.debug(f"Periodic refresh finished after {elapsed} s")
            if elapsed < interval:
                self._logger.debug(
                    f"Periodic refresh loop waiting for {interval - elapsed} s"
                )
                await asyncio.sleep(interval - elapsed)
