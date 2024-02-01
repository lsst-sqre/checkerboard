"""Exceptions for Checkerboard."""

from fastapi import status
from safir.fastapi import ClientRequestError

__all__ = ["UnknownSlackUserError", "UnknownGitHubUserError"]


class UnknownSlackUserError(ClientRequestError):
    """Slack user does not exist."""

    error = "unknown_user"
    status_code = status.HTTP_404_NOT_FOUND


class UnknownGitHubUserError(ClientRequestError):
    """GitHub user does not exist."""

    error = "unknown_user"
    status_code = status.HTTP_404_NOT_FOUND
