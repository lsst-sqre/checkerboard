"""Tests for the top-level checkerboard.app module logic."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from aiohttp import BasicAuth

from checkerboard.app import create_app
from checkerboard.config import Configuration
from tests.util import MockSlackClient

if TYPE_CHECKING:
    from aiohttp.pytest_plugin.test_utils import TestClient


async def test_refresh_interval(aiohttp_client: TestClient) -> None:
    """Test spawning of a background refresh thread.

    This test may be time-sensitive.  It assumes the first test query will
    complete before the two-second refresh window.  If this proves flaky, the
    refresh interval and pause can be increased at the cost of making the test
    suite run longer.
    """
    config = Configuration()
    config.refresh_interval = 2
    auth = BasicAuth(config.username, config.password)

    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    app = await create_app(config=config, slack=slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/slack", auth=auth)
    assert response.status == 200
    data = await response.json()
    assert data == {"U1": "githubuser"}

    # Add another user and wait for 2 seconds, which is the refresh interval.
    slack.add_user("U2", "otheruser")
    await asyncio.sleep(2)

    response = await client.get("/checkerboard/slack", auth=auth)
    assert response.status == 200
    data = await response.json()
    assert data == {"U1": "githubuser", "U2": "otheruser"}
