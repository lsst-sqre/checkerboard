"""Tests for the checkerboard.handlers.external.index module and routes."""

from __future__ import annotations

import pytest

from checkerboard.dependencies.config import config_dependency
from checkerboard.dependencies.context import context_dependency
from checkerboard.main import create_app
from tests.util import MockSlackClient, get_http_client


@pytest.mark.asyncio
async def test_get_index() -> None:
    """Test GET /app-name/ ."""
    slack = MockSlackClient()
    config = config_dependency.config()
    app = await create_app(config=config, slack=slack)
    await context_dependency.initialize(config, slack)
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
