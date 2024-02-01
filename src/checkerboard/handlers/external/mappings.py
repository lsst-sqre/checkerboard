"""Handlers for user mapping endpoints."""

__all__ = [
    "get_slack_mappings",
    "get_user_mapping_by_github",
    "get_user_mapping_by_slack",
]


from checkerboard.exceptions import UnknownSlackUserError
from checkerboard.handlers import routes


@routes.get("/slack")
async def get_slack_mappings() -> dict[str, str]:
    """GET full map of Slack users to GitHub identities.

    Response is a JSON dict mapping Slack user IDs to GitHub users for all
    known Slack users with a GitHub user configured.
    """
    mapper = request.config_dict["checkerboard/mapper"]
    return await mapper.json()


@routes.get("/slack/{slack_id}")
async def get_user_mapping_by_slack(slack_id: str) -> dict[str, str]:
    """GET map for a single user by Slack ID.

    If the given Slack user ID has a GitHub user configured, response is a
    JSON dict with one key, the Slack user ID, whose value is their GitHub
    user.  Otherwise, returns 404.
    """
    mapper = request.config_dict["checkerboard/mapper"]
    slack_id = request.match_info["slack_id"]
    github_id = await mapper.github_for_slack_user(slack_id)
    if github_id:
        return {slack_id: github_id}
    raise UnknownSlackUserError(f"Slack user {slack_id} not found")


@routes.get("/github/{github_id}")
async def get_user_mapping_by_github(str: github_id) -> dict[str, str]:
    """GET map for a single user by GitHub user.

    If the given GitHub user corresponds to a Slack user ID, response is a
    JSON dict with one key, the Slack user ID, whose value is their GitHub
    user.  Otherwise, returns 404.
    """
    mapper = request.config_dict["checkerboard/mapper"]
    github_id = request.match_info["github_id"]
    slack_id = await mapper.slack_for_github_user(github_id)
    if slack_id:
        return {slack_id: github_id}
    raise UnknownSlackUserError(
        f"Slack user for GitHub user {github_id} not found"
    )
