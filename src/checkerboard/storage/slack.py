"""Mappers for Slack users."""

from __future__ import annotations

import asyncio
import json
import logging
from random import SystemRandom
from typing import Any

import redis.asyncio as redis
from aiohttp import ClientConnectionError
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

__all__ = ["SlackGitHubMapper", "UnknownFieldError"]


class UnknownFieldError(Exception):
    """The expected Slack profile field is not defined."""


class SlackGitHubMapper:
    """Bidirectional map of Slack users to GitHub users.

    This class loads all Slack users from the native Slack workspace
    of the provided Slack AsyncWebClient (via the refresh method) and
    then retrieves their curresponding GitHub username from their
    extended profile.  It then provides methods to return all mappings
    or to return the GitHub user for a Slack user or vice versa.

    This class is thread-safe.

    Paramters
    ---------
    slack : `AsyncWebClient`
        Slack client to use for queries.  This must already have the
        authentication token set.
    profile_field_name : `str`
        The name of the custom Slack profile field that contains the GitHub
        username.
    redis_client : `redis_asyncio.Redis`
    logger : `logging.Logger`, optional
        Logger to use for status messages.  Defaults to the logger for
        __name__.
    """

    def __init__(
        self,
        slack: AsyncWebClient,
        profile_field_name: str,
        redis_client: redis.Redis,
        *,
        logger: logging.Logger | None = None,
        slack_concurrency: int = 1,
    ) -> None:
        self.slack = slack
        self.profile_field_name = profile_field_name
        self.slack_concurrency = slack_concurrency
        self.logger = logger or logging.getLogger(__name__)
        self.redis_client = redis_client
        self._profile_field_id: str | None = None
        self._slack_to_github: dict[str, str] = {}
        self._github_to_slack: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def github_for_slack_user(self, slack_id: str) -> str | None:
        """Return the GitHub user for a Slack user ID, if any.

        Parameters
        ----------
        slack_id : `str`
            The Slack user ID (not the display name or real name).

        Returns
        -------
        github_id : `str` or `None`
            The corresponding GitHub username coerced to lowercase, or None if
            that Slack user does not exist or does not have a GitHub user set
            in their profile.
        """
        async with self._lock:
            return self._slack_to_github.get(slack_id)

    async def json(self) -> str:
        """Return the map of Slack users to GitHub users as JSON.

        Returns
        -------
        json : `str`
            JSON-encoded dict of Slack user IDs to GitHub usernames.  All
            GitHub usernames are coerced to lowercase since GitHub is
            case-insensitive.
        """
        async with self._lock:
            return json.dumps(self._slack_to_github)

    async def start(self) -> None:
        """Run this on startup.  It tries a Redis connection in order
        to get the cached user data.  If it finds any, it returns
        after refreshing the internal maps; if it does not, it blocks
        until refresh() has run once, which will presumably populate
        those maps.

        The intent is to allow us to start quickly and offer service, while
        still doing the background map refresh to track user changes.
        """
        if self._slack_to_github:
            self.logger.warning(
                "Non-empty user map exists; returning from start() as it's"
                " obviously post-startup"
            )
            return
        # Get the list of users and then their profile data.
        slack_ids = await self._get_user_list()
        self.logger.debug(
            f"Returned from _get_user_list with {len(slack_ids)} candidates"
        )
        slack_to_github: dict[str, str] = {}
        github_to_slack: dict[str, str] = {}
        self.logger.debug("Consulting redis to build initial map")
        for sl_u in slack_ids:
            # If we have any of this information in Redis, load it.
            # It's all subject to change during refresh, but this information
            # changes slowly, so the idea is, we start up with our cache,
            # which is probably mostly correct, and let the refresh task
            # scheduled by our context dependency deal with updates.
            #
            # If this comes back empty, we don't have a redis cache, so we
            # will delay startup until we have done the first refresh.
            self.logger.debug(f"Redis lookup of Slack user {sl_u}")
            gh_u = await self.redis_client.get(sl_u)
            self.logger.debug(f"Lookup result {sl_u}: {gh_u}")
            if not gh_u:
                self.logger.debug(f"{sl_u} not found in Redis")
            else:
                self.logger.debug(f"{sl_u} found in Redis as {gh_u}")
                slack_to_github[sl_u] = gh_u
                github_to_slack[gh_u] = sl_u
        if not slack_to_github:
            self.logger.warning(
                "No users found in Redis cache; refreshing from Slack."
            )
            await self.refresh()
            return
        async with self._lock:
            self._slack_to_github = slack_to_github
            self._github_to_slack = github_to_slack
        return

    async def refresh(self) -> None:
        """Refresh the map of Slack users to GitHub users.

        Raises
        ------
        SlackApiError
            One of our Slack calls failed.
        UnknownFieldError
            The expected custom Slack profile field is not defined.
        """
        slack_to_github: dict[str, str] = {}
        github_to_slack: dict[str, str] = {}
        if not self._profile_field_id:
            self._profile_field_id = await self._get_profile_field_id(
                self.profile_field_name
            )

        # Get the list of users and then their profile data.
        slack_ids = await self._get_user_list()
        self.logger.debug(
            f"Returned from _get_user_list with {len(slack_ids)} candidates"
        )
        for sl_u in slack_ids:
            gh_u = await self._get_user_github(sl_u)
            if gh_u:
                self.logger.debug(f"{sl_u} Github user in Slack -> {gh_u}")
                slack_to_github[sl_u] = gh_u
                github_to_slack[gh_u] = sl_u
                self.logger.debug(f"Storing {sl_u} -> {gh_u} in Redis")
                await self.redis_client.set(sl_u, gh_u)
            else:
                r_gh_u = await self.redis_client.get(sl_u)
                if r_gh_u:
                    # This user used to exist, but doesn't anymore.
                    # Remove it from Redis and our internal map.
                    await self.redis_client.delete(sl_u)
                    async with self._lock:
                        try:
                            del self._slack_to_github[sl_u]
                            del self._github_to_slack[r_gh_u]
                        except (NameError, KeyError):
                            pass
        # Replace the cached data.
        async with self._lock:
            self._slack_to_github.update(slack_to_github)
            self._github_to_slack.update(github_to_slack)

        length = len(self._slack_to_github)
        self.logger.info(f"Refreshed GitHub map from Slack ({length} entries)")

    async def map(self) -> dict[str, str]:
        return self._slack_to_github

    async def slack_for_github_user(self, github_id: str) -> str | None:
        """Return the Slack user ID for a GitHub user, if any.

        Parameters
        ----------
        github_id : `str`
            A GitHub username (not case-sensitive).

        Returns
        -------
        slack : `str` or `None`
            The corresponding Slack user ID (not the display name or real
            name), or None if no Slack users have that GitHub user set in
            their profile.
        """
        async with self._lock:
            return self._github_to_slack.get(github_id.lower())

    async def _get_profile_field_id(self, name: str) -> str:
        """Get the Slack field ID for a custom profile field."""
        self.logger.info(f"Getting field ID for {name} profile field")
        response = await self.slack.team_profile_get()
        profile: dict[str, Any] = response.get("profile", {})
        fields: list[dict[str, Any]] = profile.get("fields", [])
        for custom_field in fields:
            if custom_field.get("label") == name and "id" in custom_field:
                field_id = custom_field["id"]
                self.logger.info(f"Field ID for {name} is {field_id}")
                return field_id

        # The custom profile field we were expecting is not defined.
        raise UnknownFieldError(f"Slack custom profile field {name} not found")

    async def _get_user_list(self) -> list[str]:
        """Return a list of Slack user IDs."""
        slack_ids: list[str] = []
        count: int = 0
        async for page in await self.slack.users_list(limit=1000):
            count += 1
            self.logger.info(f"Listing Slack users (batch {count})")
            for user in page["members"]:
                if "id" not in user:
                    continue
                if user.get("is_bot", False) or user.get("is_app_user", False):
                    self.logger.info(f"Skipping bot or app user {user['id']}")
                else:
                    slack_ids.append(user["id"])
        self.logger.info(f"Found {len(slack_ids)} Slack users")
        return slack_ids

    async def _get_user_github(self, slack_id: str) -> str | None:
        """Get the GitHub user from a given Slack ID's profile.

        Parameters
        ----------
        slack_id : `str`
            Slack user ID for which to get the corresponding GitHub user.

        Returns
        -------
        github_id : `str` or `None`
            The corresponding GitHub user if there is one, or None.  All user
            IDs are forced to lowercase since GitHub is case-insensitive.
        """
        response = await self._get_user_profile_from_slack(slack_id)
        profile = response["profile"]
        if not profile:
            return None

        try:
            display_name = profile.get("display_name_normalized", "")
            github_id = profile["fields"][self._profile_field_id]["value"]
            github_id = github_id.lower()
        except (KeyError, TypeError):
            self.logger.debug(
                f"No GitHub user found for Slack user {slack_id}"
                f" ({display_name})"
            )
            return None

        self.logger.debug(
            f"Slack user {slack_id} ({display_name}) ->"
            f" GitHub user {github_id}"
        )
        return github_id

    async def _get_user_profile_from_slack(
        self, slack_id: str
    ) -> AsyncSlackResponse:
        """Get a user profile.  Slack client will handle rate-limiting."""
        max_retries = 10
        retries = 0
        while True:
            try:
                return await self.slack.users_profile_get(user=slack_id)
            except ClientConnectionError:
                if retries >= max_retries:
                    raise
                await self._random_delay("Cannot connect to Slack")
                retries += 1

    async def _random_delay(self, reason: str) -> None:
        """Delay for a random period between 2 and 5 seconds."""
        delay = SystemRandom().randrange(2, 5)
        self.logger.warning(f"{reason}, sleeping for {delay} seconds")
        await asyncio.sleep(delay)
