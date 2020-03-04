"""Utilities, such as mock objects, for Checkerboard tests."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING
from unittest.mock import Mock

from slack import WebClient
from slack.web.slack_response import SlackResponse

if TYPE_CHECKING:
    from typing import Any, Dict, Optional


class MockSlackClient(Mock):
    def __init__(self) -> None:
        super().__init__(spec=WebClient)

    async def team_profile_get(self) -> SlackResponse:
        data = {
            "profile": {"fields": [{"label": "GitHub Username", "id": "2"}]}
        }
        return self._build_slack_response(data)

    async def users_list(
        self, *, limit: int, cursor: Optional[str] = None
    ) -> SlackResponse:
        assert not cursor
        assert limit
        data = {
            "members": [{"id": "U1", "is_app_user": False, "is_bot": False}]
        }
        return self._build_slack_response(data)

    async def users_profile_get(self, *, user: str) -> SlackResponse:
        assert user == "U1"
        data = {
            "profile": {
                "display_name_normalized": "testuser",
                "fields": {"2": {"value": "githubuser"}},
            }
        }
        return self._build_slack_response(data)

    def _build_slack_response(self, data: Dict[str, Any]) -> SlackResponse:
        """Build a fake SlackResponse containing the given data."""
        response_data = copy.deepcopy(data)
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
