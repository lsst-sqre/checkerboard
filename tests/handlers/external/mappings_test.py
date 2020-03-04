"""Tests for the checkerboard.handlers.external.mappings module and routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.util import MockSlackClient

from checkerboard.app import create_app

if TYPE_CHECKING:
    from aiohttp.pytest_plugin.test_utils import TestClient


async def test_get_slack_mappings(aiohttp_client: TestClient) -> None:
    slack = MockSlackClient()
    app = await create_app(slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/slack")
    assert response.status == 200
    data = await response.json()
    assert data == {"U1": "githubuser"}


async def test_get_user_mapping_by_slack(aiohttp_client: TestClient) -> None:
    slack = MockSlackClient()
    app = await create_app(slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/slack/U1")
    assert response.status == 200
    data = await response.json()
    assert data == {"U1": "githubuser"}

    response = await client.get("/checkerboard/slack/U2")
    assert response.status == 404

    response = await client.get("/checkerboard/slack/testuser")
    assert response.status == 404

    response = await client.get("/checkerboard/slack/githubuser")
    assert response.status == 404

    response = await client.get("/checkerboard/slack/")
    assert response.status == 404


async def test_get_user_mapping_by_github(aiohttp_client: TestClient) -> None:
    slack = MockSlackClient()
    app = await create_app(slack)
    client = await aiohttp_client(app)

    response = await client.get("/checkerboard/github/githubuser")
    assert response.status == 200
    data = await response.json()
    assert data == {"U1": "githubuser"}

    response = await client.get("/checkerboard/github/U2")
    assert response.status == 404

    response = await client.get("/checkerboard/github/testuser")
    assert response.status == 404

    response = await client.get("/checkerboard/github/")
    assert response.status == 404
