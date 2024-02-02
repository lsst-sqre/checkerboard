"""Tests for the checkerboard.handlers.external.index module and routes."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from checkerboard.app import create_app
from tests.util import MockSlackClient

if TYPE_CHECKING:
    from aiohttp.pytest_plugin.test_utils import TestClient


@pytest.mark.asyncio
async def test_get_index(aiohttp_client: TestClient) -> None:
    """Test GET /app-name/ ."""
    slack = MockSlackClient()
    app = await create_app(slack=slack)
    name = app["safir/config"].name
    client = await aiohttp_client(app)

    response = await client.get(f"/{name}/")
    assert response.status == 200
    data = await response.json()
    metadata = data["_metadata"]
    assert metadata["name"] == name
    assert isinstance(metadata["version"], str)
    assert isinstance(metadata["description"], str)
    assert isinstance(metadata["repository_url"], str)
    assert isinstance(metadata["documentation_url"], str)
