"""Tests for the checkerboard.handlers.external.mappings module and routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import BasicAuth

from checkerboard.app import create_app
from checkerboard.config import Configuration
from tests.util import MockSlackClient

if TYPE_CHECKING:
    from aiohttp.pytest_plugin.test_utils import TestClient


async def test_authentication(aiohttp_client: TestClient) -> None:
    config = Configuration()
    config.username = "test"
    config.password = "never use this password"
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    app = await create_app(config=config, slack=slack)
    client = await aiohttp_client(app)

    # Check that all the routes require authentication.
    for route in ("slack", "slack/U1", "github/githubuser"):
        response = await client.get(f"/checkerboard/{route}")
        assert response.status == 401

    # Check that all the routes reject the wrong authentication.
    auth = BasicAuth("test", "this is wrong password")
    for route in ("slack", "slack/U1", "github/githubuser"):
        response = await client.get(f"/checkerboard/{route}", auth=auth)
        assert response.status == 401

    # Finally, check that they accept the correct password.  The details of
    # the return value will be checked by other tests.
    auth = BasicAuth("test", "never use this password")
    for route in ("slack", "slack/U1", "github/githubuser"):
        response = await client.get(f"/checkerboard/{route}", auth=auth)
        assert response.status == 200


async def test_get_slack_mappings(aiohttp_client: TestClient) -> None:
    config = Configuration()
    auth = BasicAuth(config.username, config.password)
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")
    slack.add_user("U2", "otheruser")

    app = await create_app(slack=slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/slack", auth=auth)
    assert response.status == 200
    data = await response.json()
    assert data == {"U1": "githubuser", "U2": "otheruser"}


async def test_get_user_mapping_by_slack(aiohttp_client: TestClient) -> None:
    config = Configuration()
    auth = BasicAuth(config.username, config.password)
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    app = await create_app(slack=slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/slack/U1", auth=auth)
    assert response.status == 200
    data = await response.json()
    assert data == {"U1": "githubuser"}

    response = await client.get("/checkerboard/slack/U2", auth=auth)
    assert response.status == 404

    response = await client.get("/checkerboard/slack/testuser", auth=auth)
    assert response.status == 404

    response = await client.get("/checkerboard/slack/githubuser", auth=auth)
    assert response.status == 404

    response = await client.get("/checkerboard/slack/", auth=auth)
    assert response.status == 404


async def test_get_user_mapping_by_github(aiohttp_client: TestClient) -> None:
    config = Configuration()
    auth = BasicAuth(config.username, config.password)
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    app = await create_app(slack=slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/github/githubuser", auth=auth)
    assert response.status == 200
    data = await response.json()
    assert data == {"U1": "githubuser"}

    response = await client.get("/checkerboard/github/U2", auth=auth)
    assert response.status == 404

    response = await client.get("/checkerboard/github/testuser", auth=auth)
    assert response.status == 404

    response = await client.get("/checkerboard/github/", auth=auth)
    assert response.status == 404
