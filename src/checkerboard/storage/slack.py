"""Mappers for Slack users.

Notes
-----
Calls into the Slack client have to be marked with ``# type: ignore``
currently because the typing of those calls cannot handle the optionality of
the async/await interface.
"""

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
    redis : `redis_asyncio.Redis`, optional
        Configured redis client to use for talking to redis
    logger : `logging.Logger`, optional
        Logger to use for status messages.  Defaults to the logger for
        __name__.
    """

    def __init__(
        self,
        slack: AsyncWebClient,
        profile_field_name: str,
        *,
        redis: redis.Redis | None = None,
        logger: logging.Logger | None = None,
        slack_concurrency: int = 1,
    ) -> None:
        self.slack = slack
        self.profile_field_name = profile_field_name
        self.slack_concurrency = slack_concurrency
        self.logger = logger or logging.getLogger(__name__)
        self.redis = redis
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

    async def refresh(self) -> None:
        """Refresh the map of Slack users to GitHub users.

        Raises
        ------
        SlackApiError
            One of our Slack calls failed.
        UnknownFieldError
            The expected custom Slack profile field is not defined.
        """
        if not self._profile_field_id:
            self._profile_field_id = await self._get_profile_field_id(
                self.profile_field_name
            )

        # Get the list of users and then their profile data.
        slack_to_github: dict[str, str] = {}
        github_to_slack: dict[str, str] = {}
        slack_ids = await self._get_user_list()
        need_lookup: list[str] = []

        if self.redis is None:
            need_lookup = slack_ids
        else:
            for sl_u in slack_ids:
                # If the key does not exist in redis, we need to check it.
                # This is inefficient since we are always rechecking all
                # our negative-result users...but once we find someone, they
                # get stored, and will be found without a lookup.  In the
                # steady-state case, there aren't very many people we want
                # to look up who don't exist, but there are a whole bunch
                # of Slack users we're just going to keep checking in case
                # they have filled in the appropriate field.  It seems like
                # we could do better here.
                #
                # We also don't have a way to delete users, but we'll worry
                # about that later.  At worst we'll be spamming users who
                # no longer care about their Jenkins jobs but then why are
                # they running them?
                gh_u = await self.redis.get(sl_u)
                if not gh_u:
                    need_lookup.append(sl_u)
                else:
                    slack_to_github[sl_u] = gh_u
                    github_to_slack[gh_u] = sl_u
                    self.logger.info(
                        f"Checking profiles of {len(need_lookup)} Slack users"
                    )
        for sl_u in need_lookup:
            gh_u = await self._get_user_github(sl_u)
            if gh_u:
                slack_to_github[sl_u] = gh_u
                github_to_slack[gh_u] = sl_u
                if self.redis is not None:
                    await self.redis.set(sl_u, gh_u)

        # Replace the cached data.
        async with self._lock:
            self._slack_to_github = slack_to_github
            self._github_to_slack = github_to_slack

        length = len(slack_to_github)
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
                    self.logger.info("Skipping bot or app user %s", user["id"])
                else:
                    slack_ids.append(user["id"])
        self.logger.info("Found %d Slack users", len(slack_ids))
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
