"""Tests for the checkerboard.slack module."""

from __future__ import annotations

import json

from checkerboard.slack import SlackGitHubMapper
from tests.util import MockSlackClient


async def test_mapper() -> None:
    slack = MockSlackClient()
    mapper = SlackGitHubMapper(slack, "GitHub Username")

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

    # Now, run refresh.  This will test both handling of invalid users and
    # pagination, since these will be returned in two groups.
    await mapper.refresh()

    # Check that the resulting mapping is correct for valid users.
    assert mapper.github_for_slack_user("U1") == "githubuser"
    assert mapper.github_for_slack_user("U2") == "otheruser"
    assert mapper.github_for_slack_user("UNA") == "no-app"
    assert mapper.github_for_slack_user("UNB") == "no-bot"
    assert mapper.github_for_slack_user("UNN") == "no-name"

    # Check the inverse mappings and case insensitivity.
    assert mapper.slack_for_github_user("GITHUBUSER") == "U1"
    assert mapper.slack_for_github_user("otheruser") == "U2"
    assert mapper.slack_for_github_user("NO-app") == "UNA"
    assert mapper.slack_for_github_user("no-bot") == "UNB"
    assert mapper.slack_for_github_user("no-name") == "UNN"

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
        assert not mapper.github_for_slack_user(user)
        assert not mapper.slack_for_github_user(user)

    # Check that the full mapping returns the correct list.
    assert json.loads(mapper.json()) == {
        "U1": "githubuser",
        "U2": "otheruser",
        "UNA": "no-app",
        "UNB": "no-bot",
        "UNN": "no-name",
    }
