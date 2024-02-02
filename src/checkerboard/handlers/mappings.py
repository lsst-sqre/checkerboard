"""Handlers for user mapping endpoints."""

__all__ = ["router"]

from typing import Annotated

from fastapi import APIRouter, Depends

from checkerboard.dependencies.auth import auth_dependency
from checkerboard.dependencies.context import (
    RequestContext,
    context_dependency,
)
from checkerboard.exceptions import UnknownSlackUserError

router = APIRouter()


@router.get("/slack")
async def get_slack_mappings(
    context: Annotated[
        RequestContext, Depends(context_dependency), Depends(auth_dependency)
    ],
) -> dict[str, str]:
    """GET full map of Slack users to GitHub identities.

    Response is a JSON dict mapping Slack user IDs to GitHub users for all
    known Slack users with a GitHub user configured.
    """
    mapper = context_dependency.get_process_context().mapper
    return await mapper.map()


@router.get("/slack/{slack_id}")
async def get_user_mapping_by_slack(
    slack_id: str,
    context: Annotated[
        RequestContext, Depends(context_dependency), Depends(auth_dependency)
    ],
) -> dict[str, str]:
    """GET map for a single user by Slack ID.

    If the given Slack user ID has a GitHub user configured, response is a
    JSON dict with one key, the Slack user ID, whose value is their GitHub
    user.  Otherwise, returns 404.
    """
    mapper = context_dependency.get_process_context().mapper
    github_id = await mapper.github_for_slack_user(slack_id)
    if github_id:
        return {slack_id: github_id}
    raise UnknownSlackUserError(f"Slack user {slack_id} not found")


@router.get("/github/{github_id}")
async def get_user_mapping_by_github(
    github_id: str,
    context: Annotated[
        RequestContext, Depends(context_dependency), Depends(auth_dependency)
    ],
) -> dict[str, str]:
    """GET map for a single user by GitHub user.

    If the given GitHub user corresponds to a Slack user ID, response is a
    JSON dict with one key, the Slack user ID, whose value is their GitHub
    user.  Otherwise, returns 404.
    """
    mapper = context_dependency.get_process_context().mapper
    slack_id = await mapper.slack_for_github_user(github_id)
    if slack_id:
        return {slack_id: github_id}
    raise UnknownSlackUserError(
        f"Slack user for GitHub user {github_id} not found"
    )
