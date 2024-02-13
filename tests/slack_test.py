"""Tests for the checkerboard.storage.slack module."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import patch

import pytest

from checkerboard.service.mapper import Mapper
from checkerboard.storage.redis import MappingCache
from checkerboard.storage.slack import SlackGitHubMapper, UnknownFieldError
from tests.util import (
    MockRedisClient,
    MockSlackClient,
    MockSlackClientWithFailures,
)


@pytest.mark.asyncio
async def test_mapper() -> None:
    """Tests of the mapper, primarily around data parsing and robustness."""
    slack = MockSlackClient()
    redis = MappingCache(redis_client=MockRedisClient())
    slack_mapper = SlackGitHubMapper(
        slack_client=slack, redis=redis, profile_field_name="GitHub Username"
    )
    service = Mapper(slack=slack_mapper, redis=redis)

    # Add some users with and without GitHub username mappings.
    slack.add_user("U1", "githubuser")
    slack.add_user("U2", "OtherUser")
    slack.add_user("U3", None)

    # Add bots and app users with and without username mappings.
    slack.add_user("Ubot", "botuser", is_bot=True)
    slack.add_user("Ubot2", None, is_bot=True)
    slack.add_user("Uapp", "appuser", is_app_user=True)
    slack.add_user("Uapp2", None, is_app_user=True)
    slack.add_user("Uboth", "bothuser", is_bot=True, is_app_user=True)
    slack.add_user("Uboth2", None, is_bot=True, is_app_user=True)

    # Add users with no is_app_user or no is_bot.  Should be processed with a
    # valid mapping.
    slack.add_raw_user(
        "UNA",
        {"id": "UNA", "is_bot": False},
        {
            "display_name_normalized": "user",
            "fields": {"2": {"value": "no-app"}},
        },
    )
    slack.add_raw_user(
        "UNB",
        {"id": "UNB", "is_app_user": False},
        {
            "display_name_normalized": "user",
            "fields": {"2": {"value": "no-bot"}},
        },
    )

    # Add a user with no display name.  Should be processed with a valid
    # mapping.
    slack.add_raw_user(
        "UNN",
        {"id": "UNN", "is_bot": False, "is_app_user": False},
        {"fields": {"2": {"value": "no-name"}}},
    )

    # Add a user with a custom field but not the one we care about.
    slack.add_raw_user(
        "UC",
        {"id": "UC", "is_app_user": False, "is_bot": False},
        {
            "display_name_normalized": "user",
            "fields": {"1": {"value": "custom"}},
        },
    )

    # Add a user with the custom field we care about, but without a value.
    slack.add_raw_user(
        "UCV",
        {"id": "UC", "is_app_user": False, "is_bot": False},
        {"display_name_normalized": "user", "fields": {"1": {}}},
    )

    # Add some malformed users.
    slack.add_raw_user("UX1", {}, {})
    slack.add_raw_user(
        "UX2", {"id": "UX2", "is_app_user": False, "is_bot": False}, {}
    )
    slack.add_raw_user("UX3", {}, {"display_name_normalized": "foo"})
    slack.add_raw_user(
        "UX4", {}, {"display_name_normalized": "foo", "fields": {}}
    )

    # Now, run refresh.  This will test handling of invalid users.
    # Pagination is now the real slack client's problem, not ours, so we
    # don't do any cursor checking.
    await slack_mapper.refresh()
    await service.refresh()

    # Check that the resulting mapping is correct for valid users.
    assert await service.github_for_slack_user("U1") == "githubuser"
    assert await service.github_for_slack_user("U2") == "otheruser"
    assert await service.github_for_slack_user("UNA") == "no-app"
    assert await service.github_for_slack_user("UNB") == "no-bot"
    assert await service.github_for_slack_user("UNN") == "no-name"

    # Check the inverse mappings and case insensitivity.
    assert await service.slack_for_github_user("GITHUBUSER") == "U1"
    assert await service.slack_for_github_user("otheruser") == "U2"
    assert await service.slack_for_github_user("NO-app") == "UNA"
    assert await service.slack_for_github_user("no-bot") == "UNB"
    assert await service.slack_for_github_user("no-name") == "UNN"

    # Check that all the other users don't exist.
    for user in (
        "U3",
        "Ubot",
        "Ubot2",
        "Uapp",
        "Uapp2",
        "Uboth",
        "Uboth2",
        "UC",
        "UCV",
        "UX1",
        "UX2",
        "UX3",
        "UX4",
    ):
        assert not await service.github_for_slack_user(user)
        assert not await service.slack_for_github_user(user)

    # Check that the full mapping returns the correct list.
    full_map = await service.map()
    assert full_map == {
        "U1": "githubuser",
        "U2": "otheruser",
        "UNA": "no-app",
        "UNB": "no-bot",
        "UNN": "no-name",
    }


@pytest.mark.asyncio
async def test_invalid_profile_field() -> None:
    """Test handling of invalid or missing custom profile fields."""
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")
    redis = MappingCache(redis_client=MockRedisClient())
    slack_mapper = SlackGitHubMapper(
        slack_client=slack, redis=redis, profile_field_name="Other Field"
    )
    with pytest.raises(UnknownFieldError):
        await slack_mapper.refresh()

    # Test with multiple team profile custom fields, including the one we care
    # about.
    team_profile = {
        "profile": {
            "fields": [
                {"label": "Something Else", "id": "1"},
                {"label": "GitHub Username", "id": "2"},
                {"label": "Other Thing", "id": "3"},
            ]
        }
    }

    slack = MockSlackClient(team_profile=team_profile)
    slack.add_user("U1", "githubuser")
    redis = MappingCache(redis_client=MockRedisClient())
    slack_mapper = SlackGitHubMapper(
        slack_client=slack, redis=redis, profile_field_name="GitHub Username"
    )
    service = Mapper(slack=slack_mapper, redis=redis)
    await slack_mapper.refresh()
    await service.refresh()
    assert await service.github_for_slack_user("U1") == "githubuser"

    # Try a variety of invalid team profile data structures or ones where the
    # field we care about is missing.
    test_profiles: list[dict[str, Any]] = [
        {},
        {"foo": "bar"},
        {"profile": {}},
        {"profile": {"fields": []}},
        {"profile": {"fields": [{}]}},
        {"profile": {"fields": [{"label": "GitHub Username"}]}},
        {"profile": {"fields": [{"id": "2"}]}},
    ]
    for team_profile in test_profiles:
        slack = MockSlackClient(team_profile=team_profile)
        redis = MappingCache(redis_client=MockRedisClient())
        slack_mapper = SlackGitHubMapper(
            slack_client=slack,
            redis=redis,
            profile_field_name="GitHub Username",
        )
        with pytest.raises(UnknownFieldError):
            await slack_mapper.refresh()


@pytest.mark.asyncio
async def test_backoff() -> None:
    """Test backoff and retry on errors."""
    slack = MockSlackClientWithFailures()
    slack.add_user("U1", "githubuser")
    slack.add_user("U2", "otheruser")

    # Patch out the sleep to reduce waiting, and confirm that we slept for a
    # random number of seconds between 2 and 5 twice, since we should have
    # gotten two retriable failures from MockSlackClientWithFailures.
    #
    # AsyncMock was introduced in Python 3.8, so sadly we can't use it yet.
    #
    # Well, now we could, but this works just fine.
    redis = MappingCache(redis_client=MockRedisClient())
    slack_mapper = SlackGitHubMapper(
        slack_client=slack, redis=redis, profile_field_name="GitHub Username"
    )
    service = Mapper(slack=slack_mapper, redis=redis)
    with patch("asyncio.sleep") as sleep:
        sleep.return_value = asyncio.Future()
        sleep.return_value.set_result(None)
        await slack_mapper.refresh()
        assert sleep.call_count == 2
        for call in sleep.call_args_list:
            assert call[0][0] >= 2
            assert call[0][0] <= 5

    await service.refresh()
    # Check that all the data was received and recorded properly.
    assert await service.github_for_slack_user("U1") == "githubuser"
    assert await service.github_for_slack_user("U2") == "otheruser"
