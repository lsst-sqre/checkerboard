"""Mappers for Slack users."""

from __future__ import annotations

import asyncio
import random
from typing import Any

import structlog
from aiohttp import ClientConnectionError
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse
from structlog.stdlib import BoundLogger

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
    logger : `structlog.stdlib.BoundLogger`, optional
        Logger to use for status messages.  Defaults to the logger for
        __name__.
    """

    def __init__(
        self,
        slack_client: AsyncWebClient,
        redis: MappingCache,
        profile_field_name: str,
        *,
        logger: BoundLogger | None = None,
    ) -> None:
        self._slack_client = slack_client
        self._profile_field_name = profile_field_name
        self._logger = logger or structlog.get_logger(__name__)
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
        self._logger.info("Initiating map refresh")
        if not self._profile_field_id:
            self._profile_field_id = await self._get_profile_field_id(
                self._profile_field_name
            )

        # Get the list of users and then their profile data.
        slack_ids = await self._get_user_list()
        slack_count = len(slack_ids)
        redis_data = await self._redis.get_all()
        redis_ids = list(redis_data.keys())

        # First thing: anyone that exists in redis but doesn't exist in Slack
        # means they're no longer part of our Slack team, so we should
        # purge them from redis.
        await self._purge_redis_of_deleted_slack_users(slack_ids, redis_data)

        # Because we're going to get rate limited, we want to tackle this in
        # a particular order to minimize the time until we have answers for
        # our callers.
        ordered_slack_ids = self._build_ordered_slack_list(
            slack_ids, redis_data
        )

        updated_users = 0
        current_user_number = 0
        for slack_user in ordered_slack_ids:
            current_user_number += 1
            ctext = f"[{current_user_number}/{slack_count}]"
            github_user = await self._get_user_github(slack_user, ctext=ctext)
            redis_github_user = await self._redis.get(slack_user)
            if github_user:
                self._logger.debug(
                    f"Slack user {slack_user} -> Github user {github_user}"
                    f" {ctext}"
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
                self._logger.debug(
                    f"{slack_user} no longer mapped in GitHub; removing"
                    f" {redis_github_user} mapping from redis {ctext}"
                )
                # This is the distinction mentioned in the redis
                # storage layer.  The key will exist, but with an
                # empty-string value.  The only reason to do this
                # is so that we can do the list ordering to ensure
                # that we've asked Slack about everyone as soon as
                # possible.
                await self._redis.set(slack_user, "")
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

    async def _purge_redis_of_deleted_slack_users(
        self, slack_ids: list[str], redis_data: dict[str, str]
    ) -> None:
        redis_ids = list(redis_data.keys())
        slack_set = set(slack_ids)
        redis_set = set(redis_ids)
        unslacked = redis_set - slack_set
        for removed in unslacked:
            self._logger.warning(
                f"User {removed} found in redis but not Slack; removing"
            )
            await self._redis.delete(removed)
            del redis_data[removed]

    def _build_ordered_slack_list(
        self, slack_ids: list[str], redis_data: dict[str, str]
    ) -> list[str]:
        total = 0
        mapped = 0
        unmapped = 0
        slack_unmapped: list[str] = []
        slack_mapped: list[str] = []
        for redis_user in redis_data:
            total += 1
            if redis_data[redis_user] == "":
                unmapped += 1
                slack_unmapped.append(redis_user)
            else:
                mapped += 1
                slack_mapped.append(redis_user)
        self._logger.info(
            f"{total} users found in redis; {mapped} have"
            f" GitHub IDs; {unmapped} do not"
        )
        # First we want to look up anyone we've never
        # tried to find a mapping for (that is, they're not in Redis).
        #
        # Next, we want to try all the people who didn't have mappings last
        # time we looked, because maybe they updated their profile with
        # the GitHub user ID.
        #
        # Finally, we want to go through and recheck anyone who did have a
        # mapping, in case it changed, which is probably a rare event
        # (maybe they had a typo, or they put a URL instead of a username, or
        # something)
        #
        redis_ids = list(redis_data.keys())
        ordered_slack_ids = list(set(slack_ids) - set(redis_ids))
        ordered_slack_ids.extend(slack_unmapped)
        ordered_slack_ids.extend(slack_mapped)
        return ordered_slack_ids

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
                    self._logger.debug(
                        f"Skipping bot or app user {user['id']}"
                    )
                else:
                    slack_ids.append(user["id"])
        self._logger.info(f"Found {len(slack_ids)} Slack users")
        return slack_ids

    async def _get_user_github(
        self, slack_id: str, ctext: str | None = None
    ) -> str | None:
        """Get the GitHub user from a given Slack ID's profile.

        Parameters
        ----------
        slack_id : `str`
            Slack user ID for which to get the corresponding GitHub user.
        ctext: `str`
            Text to append to line (optional); it should be something like
            "[14/503]" to give a progress indicator for logging purposes.

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
            msg = (
                f"No GitHub user found for Slack user {slack_id}"
                f" ({display_name})"
            )
            if ctext:
                msg += f" {ctext}"
            self._logger.debug(msg)
            return None

        msg = (
            f"Slack user {slack_id} ({display_name}) ->"
            f" GitHub user {github_id}"
        )
        if ctext:
            msg += f" {ctext}"
        self._logger.debug(msg)
        return github_id

    async def _get_user_profile_from_slack(
        self, slack_id: str
    ) -> AsyncSlackResponse:
        """Get a user profile.  Slack client will handle rate-limiting."""
        max_retries = 5
        retries = 0
        last_exc: ClientConnectionError | TimeoutError | None = None
        while retries < max_retries:
            try:
                async with asyncio.timeout(60):
                    # I don't know why we aren't timing out already.
                    return await self._slack_client.users_profile_get(
                        user=slack_id
                    )
            except (TimeoutError, ClientConnectionError) as exc:
                await self._random_delay(f"Cannot connect to Slack: {exc}")
                last_exc = exc
                retries += 1
        if last_exc is not None:
            raise last_exc
        # We should not get here; it will bubble up as a 500 if we do.
        raise RuntimeError(f"Could not get Slack profile for {slack_id}")

    async def _random_delay(self, reason: str) -> None:
        """Delay for a random period between 2 and 5 (integral) seconds
        inclusive.
        """
        # This really doesn't need to be cryptographically secure.
        delay = random.randrange(2, 6)  # noqa: S311
        self._logger.warning(f"{reason}, sleeping for {delay} seconds")
        await asyncio.sleep(delay)
