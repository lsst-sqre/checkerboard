"""Tests for the top-level checkerboard.main module logic."""

from __future__ import annotations

import asyncio

import pytest
from asgi_lifespan import LifespanManager

from checkerboard.config import Configuration
from checkerboard.main import create_app
from tests.util import MockRedisClient, MockSlackClient, get_http_client


@pytest.mark.asyncio
async def test_refresh_interval() -> None:
    """Test spawning of a background refresh thread.

    This test may be time-sensitive.  It assumes the first test query will
    complete before the two-second refresh window.  If this proves flaky, the
    refresh interval and pause can be increased at the cost of making the test
    suite run longer.
    """
    config = Configuration()
    config.refresh_interval = 2

    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    redis_client = MockRedisClient()

    app = create_app(
        config=config, slack_client=slack, redis_client=redis_client
    )
    async with LifespanManager(app):
        client = get_http_client(app)

        response = await client.get("/checkerboard/slack")
        assert response.status_code == 200
        data = response.json()
        assert data == {"U1": "githubuser"}

        # Add another user and wait for 2 seconds, which is the refresh
        # interval.
        slack.add_user("U2", "otheruser")
        # Make sure it's not there yet; this is racy but hopefully fast enough
        # that it always passes.
        response = await client.get("/checkerboard/slack")
        assert response.status_code == 200
        data = response.json()
        assert data == {"U1": "githubuser"}

        # Wait for refresh.
        await asyncio.sleep(2)

        response = await client.get("/checkerboard/slack")
        assert response.status_code == 200
        data = response.json()
        assert data == {"U1": "githubuser", "U2": "otheruser"}
