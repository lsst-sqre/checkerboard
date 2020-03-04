"""Mappers for Slack users."""

from __future__ import annotations

import asyncio
import json
import logging
from random import SystemRandom
from threading import Lock
from typing import TYPE_CHECKING

from aiohttp import ClientConnectionError
from slack.errors import SlackApiError

if TYPE_CHECKING:
    from slack import WebClient
    from slack.web.slack_response import SlackResponse
    from typing import Dict, List, Optional

__all__ = ["SlackGitHubMapper", "UnknownFieldError"]


class UnknownFieldError(Exception):
    """The expected Slack profile field is not defined."""


class SlackGitHubMapper(object):
    """Bidirectional map of Slack users to GitHub users.

    This class loads all Slack users from the native Slack workspace of the
    provided Slack WebClient (via the refresh method) and then retrieves their
    curresponding GitHub username from their extended profile.  It then
    provides methods to return all mappings or to return the GitHub user for a
    Slack user or vice versa.

    This class is thread-safe.

    Paramters
    ---------
    slack : `WebClient`
        Slack client to use for queries.  This must already have the
        authentication token set and must be created with ``run_async`` set.
    profile_field_name : `str`
        The name of the custom Slack profile field that contains the GitHub
        username.
    slack_concurrency : `int`, optional
        The number of concurrent requests to make to the Slack API.  Setting
        this too high will cause Slack to rate-limit profile queries, which
        will be handled by pausing and will slow down the mapping.
    """

    def __init__(
        self,
        slack: WebClient,
        profile_field_name: str,
        *,
        slack_concurrency: int = 1,
    ) -> None:
        self.slack = slack
        self.profile_field_name = profile_field_name
        self.slack_concurrency = slack_concurrency
        self._profile_field_id: Optional[str] = None
        self._slack_to_github: Dict[str, str] = {}
        self._github_to_slack: Dict[str, str] = {}
        self._lock = Lock()

    def github_for_slack_user(self, user: str) -> Optional[str]:
        """Return the GitHub user for a Slack user ID, if any.

        Parameters
        ----------
        user : `str`
            The Slack user ID (not the display name or real name).

        Returns
        -------
        github : `str` or `None`
            The corresponding GitHub username coerced to lowercase, or None if
            that Slack user does not exist or does not have a GitHub user set
            in their profile.
        """
        with self._lock:
            return self._slack_to_github.get(user)

    def json(self) -> str:
        """Return the map of Slack users to GitHub users as JSON.

        Returns
        -------
        json : `str`
            JSON-encoded dict of Slack user IDs to GitHub usernames.  All
            GitHub usernames are coerced to lowercase since GitHub is
            case-insensitive.
        """
        with self._lock:
            result = json.dumps(self._slack_to_github)
        return result

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

        # Get the list of users and then their profile data, enforcing a
        # concurrency limit on the profile fetches.
        slack_to_github: Dict[str, str] = {}
        users = await self._get_user_list()
        semaphore = asyncio.Semaphore(self.slack_concurrency)
        github_aws = [self._get_user_github(u, semaphore) for u in users]
        github_users = await asyncio.gather(*github_aws)
        for user, github in zip(users, github_users):
            if github:
                slack_to_github[user] = github
        github_to_slack = {g: u for u, g in slack_to_github.items()}

        # Replace the cached data.
        with self._lock:
            self._slack_to_github = slack_to_github
            self._github_to_slack = github_to_slack

        length = len(slack_to_github)
        logging.info("Refreshed GitHub map from Slack (%d entries)", length)

    def slack_for_github_user(self, user: str) -> Optional[str]:
        """Return the Slack user ID for a GitHub user, if any.

        Parameters
        ----------
        user : `str`

        Returns
        -------
        slack : `str` or `None`
            The corresponding Slack user ID (not the display name or real
            name), or None if no Slack users have that GitHub user set in
            their profile.
        """
        with self._lock:
            return self._github_to_slack.get(user.lower())

    async def _get_profile_field_id(self, name: str) -> str:
        """Get the Slack field ID for a custom profile field."""
        logging.info("Getting field ID for %s profile field", name)
        response = await self.slack.team_profile_get()
        for custom_field in response.get("profile", {}).get("fields", []):
            if custom_field.get("label") == name and "id" in custom_field:
                field_id = custom_field["id"]
                logging.info("Field ID for %s is %s", name, field_id)
                return field_id

        # The custom profile field we were expecting is not defined.
        raise UnknownFieldError(f"Slack custom profile field {name} not found")

    async def _get_user_list(self) -> List[str]:
        """Return a list of Slack user IDs.

        Notes
        -----
        We can't use the built-in pagination support of SlackResponse because
        it isn't async-aware, so do the equivalent manually.
        """
        users: List[str] = []
        batch = 1
        logging.info("Listing Slack users (batch %d)", batch)
        response = await self.slack.users_list(limit=1000)
        while True:
            for user in response["members"]:
                if "id" not in user:
                    continue
                if user.get("is_bot", False) or user.get("is_app_user", False):
                    logging.info("Skipping bot or app user %s", user["id"])
                else:
                    users.append(user["id"])
            cursor = response.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
            batch += 1
            logging.info("Listing Slack users (batch %d)", batch)
            response = await self.slack.users_list(cursor=cursor, limit=1000)
        logging.info("Found %d Slack users", len(users))
        return users

    async def _get_user_github(
        self, user: str, semaphore: asyncio.Semaphore
    ) -> Optional[str]:
        """Get the GitHub user from a given user's profile.

        Parameters
        ----------
        user : `str`
            Slack user ID for which to get the corresponding GitHub user.
        semaphore : `asyncio.Semaphore`
            Semaphore controlling Slack API calls, used to avoid overruning
            Slack's rate limits and opening too many connections to their
            servers.

        Returns
        -------
        github : `str` or `None`
            The corresponding GitHub user if there is one, or None.  All user
            IDs are forced to lowercase since GitHub is case-insensitive.
        """
        async with semaphore:
            response = await self._get_user_profile(user)
        profile = response["profile"]
        if not profile:
            return None

        try:
            display_name = profile.get("display_name_normalized", "")
            github = profile["fields"][self._profile_field_id]["value"].lower()
        except (KeyError, TypeError):
            logging.info(
                "No GitHub user found for Slack user %s (%s)",
                user,
                display_name,
            )
            return None

        logging.info(
            "Slack user %s (%s) -> GitHub user %s", user, display_name, github
        )
        return github

    async def _get_user_profile(self, user: str) -> SlackResponse:
        """Get a user profile, handling retrying for rate limiting."""
        while True:
            try:
                response = await self.slack.users_profile_get(user=user)
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

    @staticmethod
    async def _random_delay(reason: str) -> None:
        """Delay for a random period between 2 and 5 seconds."""
        delay = SystemRandom().randrange(2, 5)
        logging.warning("%s, sleeping for %d seconds", reason, delay)
        await asyncio.sleep(delay)
