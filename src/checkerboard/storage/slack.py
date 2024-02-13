"""Mappers for Slack users."""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any

from aiohttp import ClientConnectionError
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

from ..storage.redis import MappingCache

__all__ = ["SlackGitHubMapper", "UnknownFieldError"]


class UnknownFieldError(Exception):
    """The expected Slack profile field is not defined."""


class SlackGitHubMapper:
    """Map Slack users to GitHub users.

    This class loads all Slack users from the native Slack workspace
    of the provided Slack AsyncWebClient (via the refresh method) and
    then retrieves their curresponding GitHub username (if any) from
    their extended profile.  It stores this data in its associated
    redis instance where the mapping service can retrieve it for the
    service user.

    Parameters
    ----------
    slack_client : `AsyncWebClient`
        Slack client to use for queries.  This must already have the
        authentication token set.
    redis : `checkerboard.services.redis.MappingCache`
        The redis storage layer client, which is a thin wrapper over a
        redis asyncio client that provides value canonicalization.
    profile_field_name : `str`
        The name of the custom Slack profile field that contains the GitHub
        username.
    logger : `logging.Logger`, optional
        Logger to use for status messages.  Defaults to the logger for
        __name__.
    """

    def __init__(
        self,
        slack_client: AsyncWebClient,
        redis: MappingCache,
        profile_field_name: str,
        *,
        logger: logging.Logger | None = None,
    ) -> None:
        self._slack_client = slack_client
        self._profile_field_name = profile_field_name
        self._logger = logger or logging.getLogger(__name__)
        self._redis = redis
        self._profile_field_id: str | None = None

    async def refresh(self) -> bool:
        """Refresh the map of Slack users to GitHub users.

        Returns
        -------
           True if the map changed, false if it did not

        Raises
        ------
        SlackApiError
            One of our Slack calls failed.
        UnknownFieldError
            The expected custom Slack profile field is not defined.
        """
        self._logger.debug("Initiating map refresh")
        if not self._profile_field_id:
            self._profile_field_id = await self._get_profile_field_id(
                self._profile_field_name
            )

        # Get the list of users and then their profile data.
        slack_ids = await self._get_user_list()
        self._logger.debug(
            f"Returned from _get_user_list with {len(slack_ids)} candidates"
        )
        redis_ids = await self._redis.keys()
        self._logger.debug(f"{len(redis_ids)} users found in redis")
        updated_users = 0
        for slack_user in slack_ids:
            github_user = await self._get_user_github(slack_user)
            redis_github_user = await self._redis.get(slack_user)
            if github_user:
                self._logger.debug(
                    f"Slack user {slack_user} -> Github user {github_user}"
                )
                if redis_github_user:
                    self._logger.debug(
                        f"Found redis mapping {slack_user} ->"
                        f" {redis_github_user}"
                    )
                if slack_user in redis_ids:
                    if redis_github_user == github_user:
                        self._logger.debug(
                            f"{slack_user} -> {github_user} already in redis"
                        )
                        continue
                    self._logger.debug(
                        f"{slack_user} now {github_user}; changing from"
                        f" {redis_github_user} in redis"
                    )
                self._logger.debug(
                    f"Storing {slack_user} -> {github_user} in redis"
                )
                await self._redis.set(slack_user, github_user)
                updated_users += 1
            elif redis_github_user:
                # This user used to exist, but doesn't anymore.
                # Remove it from Redis and our internal map.
                self._logger.debug(
                    f"{slack_user} no longer mapped in GitHub; removing"
                    f" {redis_github_user} mapping from redis"
                )
                await self._redis.delete(slack_user)
                updated_users += 1
        # Replace the cached data if necessary
        changed = updated_users != 0
        if changed:
            self._logger.info(
                f"Refreshed GitHub map from Slack; {updated_users}"
                " users changed"
            )
        else:
            self._logger.info(
                "Refreshed GitHub map from Slack; it was unchanged"
            )
        return changed

    async def _get_profile_field_id(self, name: str) -> str:
        """Get the Slack field ID for a custom profile field."""
        self._logger.info(f'Getting field ID for "{name}" profile field')
        response = await self._slack_client.team_profile_get()
        profile: dict[str, Any] = response.get("profile", {})
        fields: list[dict[str, Any]] = profile.get("fields", [])
        for custom_field in fields:
            if custom_field.get("label") == name and "id" in custom_field:
                field_id = custom_field["id"]
                self._logger.info(f"Field ID for {name} is {field_id}")
                return field_id

        # The custom profile field we were expecting is not defined.
        raise UnknownFieldError(
            f'Slack custom profile field "{name}" not found'
        )

    async def _get_user_list(self) -> list[str]:
        """Return a list of Slack user IDs."""
        slack_ids: list[str] = []
        count: int = 0
        async for page in await self._slack_client.users_list(limit=1000):
            count += 1
            self._logger.info(f"Listing Slack users (batch {count})")
            for user in page["members"]:
                if "id" not in user:
                    continue
                if user.get("is_bot", False) or user.get("is_app_user", False):
                    self._logger.info(f"Skipping bot or app user {user['id']}")
                else:
                    slack_ids.append(user["id"])
        self._logger.info(f"Found {len(slack_ids)} Slack users")
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
            self._logger.debug(
                f"No GitHub user found for Slack user {slack_id}"
                f" ({display_name})"
            )
            return None

        self._logger.debug(
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
                return await self._slack_client.users_profile_get(
                    user=slack_id
                )
            except ClientConnectionError:
                if retries >= max_retries:
                    raise
                await self._random_delay("Cannot connect to Slack")
                retries += 1

    async def _random_delay(self, reason: str) -> None:
        """Delay for a random period between 2 and 5 (integral) seconds
        inclusive.
        """
        # This really doesn't need to be cryptographically secure.
        delay = random.randrange(2, 6)  # noqa: S311
        self._logger.warning(f"{reason}, sleeping for {delay} seconds")
        await asyncio.sleep(delay)
