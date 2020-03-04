"""Tests for the checkerboard.handlers.external.mappings module and routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiohttp import BasicAuth

from checkerboard.app import create_app
from checkerboard.config import Configuration
from tests.util import MockSlackClient

if TYPE_CHECKING:
    from aiohttp.pytest_plugin.test_utils import TestClient


async def test_get_slack_mappings(aiohttp_client: TestClient) -> None:
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")
    slack.add_user("U2", "otheruser")

    app = await create_app(slack=slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/slack")
    assert response.status == 401

    config = Configuration()
    auth = BasicAuth(config.username, config.password)
    response = await client.get("/checkerboard/slack", auth=auth)
    assert response.status == 200
    data = await response.json()
    assert data == {"U1": "githubuser", "U2": "otheruser"}


async def test_get_user_mapping_by_slack(aiohttp_client: TestClient) -> None:
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    app = await create_app(slack=slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/slack/U1")
    assert response.status == 401

    response = await client.get("/checkerboard/slack/githubuser")
    assert response.status == 401

    config = Configuration()
    auth = BasicAuth(config.username, config.password)
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
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    app = await create_app(slack=slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/github/githubuser")
    assert response.status == 401

    response = await client.get("/checkerboard/github/U2")
    assert response.status == 401

    config = Configuration()
    auth = BasicAuth(config.username, config.password)
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
