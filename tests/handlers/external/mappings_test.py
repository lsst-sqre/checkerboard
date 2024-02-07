"""Tests for the checkerboard.handlers.external.mappings module and routes."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager
from httpx import AsyncClient, BasicAuth

from checkerboard.config import Configuration
from checkerboard.main import create_app
from tests.util import MockSlackClient, get_http_client


@pytest.mark.asyncio
async def test_authentication() -> None:
    config = Configuration()
    config.username = "test"
    config.password = "never use this password"
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    app = create_app(config=config, slack=slack)
    async with LifespanManager(app):
        client = get_http_client(app)
        assert client.auth is not None
        unauthed_client = AsyncClient(app=app, base_url="https://example.com")

        # Check that all the routes require authentication.
        for route in ("slack", "slack/U1", "github/githubuser"):
            response = await unauthed_client.get(f"/checkerboard/{route}")
            assert response.status_code == 401

        # Check that all the routes reject the wrong authentication.
        badauth_client = AsyncClient(
            app=app,
            base_url="https://example.com",
            auth=BasicAuth("test", "this is wrong password"),
        )
        for route in ("slack", "slack/U1", "github/githubuser"):
            response = await badauth_client.get(f"/checkerboard/{route}")
            assert response.status_code == 401

        # Finally, check that they accept the correct password.  The details of
        # the return value will be checked by other tests.
        for route in ("slack", "slack/U1", "github/githubuser"):
            response = await client.get(f"/checkerboard/{route}")
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_get_slack_mappings() -> None:
    config = Configuration()
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")
    slack.add_user("U2", "otheruser")

    app = create_app(config=config, slack=slack)
    async with LifespanManager(app):
        client = get_http_client(app)

        response = await client.get("/checkerboard/slack")
        assert response.status_code == 200
        data = response.json()
        assert data == {"U1": "githubuser", "U2": "otheruser"}


@pytest.mark.asyncio
async def test_get_user_mapping_by_slack() -> None:
    config = Configuration()
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    app = create_app(config=config, slack=slack)
    async with LifespanManager(app):
        client = get_http_client(app)

        response = await client.get("/checkerboard/slack/U1")
        assert response.status_code == 200
        data = response.json()
        assert data == {"U1": "githubuser"}

        response = await client.get("/checkerboard/slack/U2")
        assert response.status_code == 404

        response = await client.get("/checkerboard/slack/testuser")
        assert response.status_code == 404

        response = await client.get("/checkerboard/slack/githubuser")
        assert response.status_code == 404

        response = await client.get("/checkerboard/slack/")
        assert response.status_code == 200
        data = response.json()
        assert data == {"U1": "githubuser"}


@pytest.mark.asyncio
async def test_get_user_mapping_by_github() -> None:
    config = Configuration()
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")

    app = create_app(config=config, slack=slack)
    async with LifespanManager(app):
        client = get_http_client(app)

        response = await client.get("/checkerboard/github/githubuser")
        assert response.status_code == 200
        data = response.json()
        assert data == {"U1": "githubuser"}

        response = await client.get("/checkerboard/github/U2")
        assert response.status_code == 404

        response = await client.get("/checkerboard/github/testuser")
        assert response.status_code == 404

        response = await client.get("/checkerboard/github/")
        assert response.status_code == 404
