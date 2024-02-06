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

from aiohttp import ClientConnectionError
from slack_sdk.errors import SlackApiError
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
    logger : `logging.Logger`, optional
        Logger to use for status messages.  Defaults to the logger for
        __name__.
    slack_concurrency : `int`, optional
        The number of concurrent requests to make to the Slack API.  Setting
        this too high will cause Slack to rate-limit profile queries, which
        will be handled by pausing and will slow down the mapping.
    """

    def __init__(
        self,
        slack: AsyncWebClient,
        profile_field_name: str,
        *,
        logger: logging.Logger | None = None,
        slack_concurrency: int = 1,
    ) -> None:
        self.slack = slack
        self.profile_field_name = profile_field_name
        self.slack_concurrency = slack_concurrency
        self.logger = logger or logging.getLogger(__name__)
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
        slack_ids = await self._get_user_list()
        # The whole scatter/gather thing is probably useless, given that
        # the Slack rate limit is generally quite low.  We might just
        # want to roll this into a one-at-a-time loop.
        semaphore = asyncio.Semaphore(self.slack_concurrency)
        github_awaits = [
            self._get_user_github(u, semaphore) for u in slack_ids
        ]
        self.logger.info(f"Checking profiles of {len(slack_ids)} Slack users")
        github_ids = await asyncio.gather(*github_awaits)
        for slack_id, github_id in zip(slack_ids, github_ids, strict=False):
            if github_id:
                slack_to_github[slack_id] = github_id
        github_to_slack = {g: u for u, g in slack_to_github.items()}

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

    async def _get_user_github(
        self, slack_id: str, semaphore: asyncio.Semaphore
    ) -> str | None:
        """Get the GitHub user from a given Slack ID's profile.

        Parameters
        ----------
        slack_id : `str`
            Slack user ID for which to get the corresponding GitHub user.
        semaphore : `asyncio.Semaphore`
            Semaphore controlling Slack API calls, used to avoid overruning
            Slack's rate limits and opening too many connections to their
            servers.

        Returns
        -------
        github_id : `str` or `None`
            The corresponding GitHub user if there is one, or None.  All user
            IDs are forced to lowercase since GitHub is case-insensitive.
        """
        async with semaphore:
            response = await self._get_user_profile(slack_id)
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

    async def _get_user_profile(self, slack_id: str) -> AsyncSlackResponse:
        """Get a user profile, handling retrying for rate limiting."""
        while True:
            try:
                response = await self.slack.users_profile_get(user=slack_id)
            except SlackApiError as e:
                if e.response["error"] == "ratelimited":
                    await self._random_delay("Rate-limited")
                    continue
                raise
            except ClientConnectionError:
                await self._random_delay("Cannot connect to Slack")
                continue
            else:
                return response

    async def _random_delay(self, reason: str) -> None:
        """Delay for a random period between 2 and 5 seconds."""
        delay = SystemRandom().randrange(2, 5)
        self.logger.warning("%s, sleeping for %d seconds", reason, delay)
        await asyncio.sleep(delay)
