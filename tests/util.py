"""Utilities, such as mock objects, for Checkerboard tests."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from random import SystemRandom
from typing import Any
from unittest.mock import Mock

from fastapi import FastAPI
from httpx import AsyncClient, ConnectError
from slack import WebClient  # type: ignore[attr-defined]
from slack.errors import SlackApiError
from slack.web.slack_response import SlackResponse

from checkerboard.dependencies.config import config_dependency


def get_http_client(app: FastAPI) -> AsyncClient:
    return AsyncClient(
        app=app,
        base_url="https://example.com",
        auth=(
            config_dependency.config().username,
            config_dependency.config().password,
        ),
    )


@dataclass
class MockUser:
    github: str | None
    is_bot: bool
    is_app_user: bool


class MockSlackClient(Mock):
    def __init__(self, *, team_profile: dict[str, Any] | None = None) -> None:
        super().__init__(spec=WebClient)
        self.team_profile = team_profile
        self._users: dict[str, MockUser] = {}
        self._raw_users: list[dict[str, Any]] = []
        self._raw_user_profiles: dict[str, dict[str, Any]] = {}
        self._pending: list[dict[str, dict[str, Any]]] = []

    def add_user(
        self,
        user: str,
        github: str | None,
        is_bot: bool = False,
        is_app_user: bool = False,
    ) -> None:
        """Add a user with a GitHub mapping.

        Parameters
        ----------
        user : `str`
            The Slack user ID.
        github : `str` or `None`
            The GitHub user or None to add a user without a mapping.
        is_bot : `bool`, optional
            Set to true to add a bot user.
        is_app_user : `bool`, optional
            Set to true to add an app user.
        """
        self._users[user] = MockUser(
            github=github, is_bot=is_bot, is_app_user=is_app_user
        )

    def add_raw_user(
        self,
        name: str,
        list_data: dict[str, Any],
        profile_data: dict[str, Any],
    ) -> None:
        """Add raw list and profile information for a user.

        Used to simulate errors, ignored users, and other cases where the test
        needs full control over what is included.

        Parameters
        ----------
        name : `str`
            The Slack user ID of the user.
        list_data : `Dict` [`str`, `Any`]
            Data returned for tha user from the ``users.list`` Slack endpoint.
        profile_data : `Dict` [`str`, `Any`]
            Data returned for the user from the ``users.profile.get`` Slack
            endpoint.
        """
        self._raw_users.append(list_data)
        self._raw_user_profiles[name] = profile_data

    def build_slack_response(self, data: dict[str, Any]) -> SlackResponse:
        """Build a fake SlackResponse containing the given data."""
        response_data = copy.deepcopy(data)
        if "ok" not in response_data:
            response_data["ok"] = True
        return SlackResponse(
            client=self,
            http_verb="GET",
            api_url="/mock",
            req_args={},
            data=response_data,
            headers={},
            status_code=200,
        )

    async def team_profile_get(self) -> SlackResponse:
        if self.team_profile is not None:
            data = self.team_profile
        else:
            data = {
                "profile": {
                    "fields": [{"label": "GitHub Username", "id": "2"}]
                }
            }
        return self.build_slack_response(data)

    async def users_list(
        self, *, limit: int, cursor: str | None = None
    ) -> SlackResponse:
        assert limit
        members = self._build_user_list()

        # Regardless of what limit is, return only the first five elements
        # without a cursor and everything else with the (right) cursor.
        if cursor:
            assert cursor == "some-cursor"
            assert self._pending
            data = {
                "members": self._pending,
                "response_metadata": {"next_cursor": ""},
            }
            self._pending = []
        else:
            assert not self._pending
            data = {"members": members[:5]}
            if len(members) > 5:
                data["response_metadata"] = {"next_cursor": "some-cursor"}
                self._pending = members[5:]
            else:
                data["response_metadata"] = {"next_cursor": ""}

        return self.build_slack_response(data)

    async def users_profile_get(self, *, user: str) -> SlackResponse:
        assert user in self._users or user in self._raw_user_profiles

        if user in self._users:
            profile: dict[str, Any] = {"display_name_normalized": "user"}
            if self._users[user].github:
                profile["fields"] = {"2": {"value": self._users[user].github}}
            data = {"profile": profile}
        else:
            data = {"profile": self._raw_user_profiles[user]}

        return self.build_slack_response(data)

    def _build_user_list(self) -> list[dict[str, Any]]:
        """Build the full members element of the users.list endpoint.

        This randomizes the order in which the users are listed to flush out
        any assumptions about list ordering.
        """
        members: list[dict[str, Any]] = []

        for user, mock_user in self._users.items():
            members.append(
                {
                    "id": user,
                    "is_app_user": mock_user.is_app_user,
                    "is_bot": mock_user.is_bot,
                }
            )
        members.extend(self._raw_users)

        SystemRandom().shuffle(members)
        return members


class MockSlackClientWithFailures(MockSlackClient):
    """Mock Slack client that tests failures and retries.

    Override users_profile_get to iterate between throwing a
    ConnectError, returning success, throwing a throws a rate limit
    error, and then returning success.
    """

    def __init__(self) -> None:
        super().__init__()
        self._step = 0

    async def users_profile_get(self, *, user: str) -> SlackResponse:
        step = self._step
        self._step = (self._step + 1) % 4

        if step == 0:
            raise ConnectError("Could not connect to Slack")
        if step == 1:
            return await super().users_profile_get(user=user)
        elif step == 2:
            response = self.build_slack_response(
                {"ok": False, "error": "ratelimited"}
            )
            raise SlackApiError("test exception", response)
        elif step == 3:
            return await super().users_profile_get(user=user)
        else:
            raise NotImplementedError("invalid step number")
