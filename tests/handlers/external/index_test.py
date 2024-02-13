"""Tests for the checkerboard.handlers.external.index module and routes."""

from __future__ import annotations

import pytest
from asgi_lifespan import LifespanManager

from checkerboard.dependencies.config import config_dependency
from checkerboard.main import create_app
from tests.util import MockRedisClient, MockSlackClient, get_http_client


@pytest.mark.asyncio
async def test_get_index() -> None:
    """Test GET /app-name/ ."""
    slack = MockSlackClient()
    redis_client = MockRedisClient()
    config = config_dependency.config()
    app = create_app(
        config=config, slack_client=slack, redis_client=redis_client
    )
    async with LifespanManager(app):
        name = config.name
        client = get_http_client(app)
        response = await client.get(f"/{name}/")
        assert response.status_code == 200
        data = response.json()
        metadata = data["_metadata"]
        assert metadata["name"] == name
        assert isinstance(metadata["version"], str)
        assert isinstance(metadata["description"], str)
        assert isinstance(metadata["repository_url"], str)
