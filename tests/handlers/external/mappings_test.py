"""Tests for the checkerboard.handlers.external.mappings module and routes."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager

from checkerboard.config import Configuration
from checkerboard.main import create_app
from tests.util import MockRedisClient, MockSlackClient, get_http_client


@pytest.mark.asyncio
async def test_get_slack_mappings() -> None:
    config = Configuration()
    slack = MockSlackClient()
    slack.add_user("U1", "githubuser")
    slack.add_user("U2", "otheruser")
    redis_client = MockRedisClient()

    app = create_app(config=config, slack=slack, redis_client=redis_client)
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

    redis_client = MockRedisClient()

    app = create_app(config=config, slack=slack, redis_client=redis_client)
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

    redis_client = MockRedisClient()

    app = create_app(config=config, slack=slack, redis_client=redis_client)
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
