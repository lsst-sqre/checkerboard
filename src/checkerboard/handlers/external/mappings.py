"""Handlers for user mapping endpoints."""

__all__ = [
    "get_slack_mappings",
    "get_user_mapping_by_github",
    "get_user_mapping_by_slack",
]

from aiohttp import web

from checkerboard.handlers import routes


@routes.get("/slack")
async def get_slack_mappings(request: web.Request) -> web.Response:
    """GET full map of Slack users to GitHub identities.

    Response is a JSON dict mapping Slack user IDs to GitHub users for all
    known Slack users with a GitHub user configured.
    """
    mapper = request.config_dict["checkerboard/mapper"]
    return web.Response(text=mapper.json(), content_type="application/json")


@routes.get("/slack/{user}")
async def get_user_mapping_by_slack(request: web.Request) -> web.Response:
    """GET map for a single user by Slack ID.

    If the given Slack user ID has a GitHub user configured, response is a
    JSON dict with one key, the Slack user ID, whose value is their GitHub
    user.  Otherwise, returns 404.
    """
    mapper = request.config_dict["checkerboard/mapper"]
    user = request.match_info["user"]
    github = mapper.github_for_slack_user(user)
    if github:
        return web.json_response({user: github})
    else:
        return web.Response(status=404, text=f"Slack user {user} not found")


@routes.get("/github/{user}")
async def get_user_mapping_by_github(request: web.Request) -> web.Response:
    """GET map for a single user by GitHub user.

    If the given GitHub user corresponds to a Slack user ID, response is a
    JSON dict with one key, the Slack user ID, whose value is their GitHub
    user.  Otherwise, returns 404.
    """
    mapper = request.config_dict["checkerboard/mapper"]
    user = request.match_info["user"]
    slack = mapper.slack_for_github_user(user)
    if slack:
        return web.json_response({slack: user})
    else:
        msg = f"Slack user for GitHub user {user} not found"
        return web.Response(status=404, text=msg)
