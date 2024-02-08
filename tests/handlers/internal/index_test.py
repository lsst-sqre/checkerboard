"""Tests for the checkerboard.handlers.internal.index module and routes."""

import pytest
from asgi_lifespan import LifespanManager

from checkerboard.dependencies.config import config_dependency
from checkerboard.main import create_app
from tests.util import MockRedisClient, MockSlackClient, get_http_client


@pytest.mark.asyncio
async def test_get_index() -> None:
    """Test GET / ."""
    slack = MockSlackClient()
    redis_client = MockRedisClient()
    app = create_app(slack=slack, redis_client=redis_client)
    async with LifespanManager(app):
        client = get_http_client(app)

        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == config_dependency.config().name
        assert isinstance(data["version"], str)
        assert isinstance(data["description"], str)
        assert isinstance(data["repository_url"], str)
