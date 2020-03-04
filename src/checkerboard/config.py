"""Configuration definition."""

__all__ = ["Configuration"]

import os
from dataclasses import dataclass


@dataclass
class Configuration:
    """Configuration for checkerboard."""

    name = os.getenv("SAFIR_NAME", "checkerboard")
    """The application's name, which doubles as the root HTTP endpoint path.

    Set with the ``SAFIR_NAME`` environment variable.
    """

    profile = os.getenv("SAFIR_PROFILE", "development")
    """Application run profile: "development" or "production".

    Set with the ``SAFIR_PROFILE`` environment variable.
    """

    logger_name = os.getenv("SAFIR_LOGGER", "checkerboard")
    """The root name of the application's logger.

    Set with the ``SAFIR_LOGGER`` environment variable.
    """

    log_level = os.getenv("SAFIR_LOG_LEVEL", "INFO")
    """The log level of the application's logger.

    Set with the ``SAFIR_LOG_LEVEL`` environment variable.
    """

    profile_field = os.getenv("CHECKERBOARD_PROFILE_FIELD", "GitHub Username")
    """Name of the Slack custom profile field containing the GitHub username.

    Set with the ``CHECKERBOARD_PROFILE_FIELD`` environment variable.
    """

    refresh_interval = int(os.getenv("CHECKERBOARD_REFRESH_INTERVAL", "3600"))
    """How frequently (in seconds) to refresh the Slack <-> GitHub mapping.

    Set with the ``CHECKERBOARD_REFRESH_INTERVAL`` environment variable.
    """

    slack_token = os.getenv("CHECKERBOARD_SLACK_TOKEN", "")
    """The Slack token to use for queries.

    Must be a bot token with users:read and users.profile:read scopes.  Set
    with the ``CHECKERBOARD_SLACK_TOKEN`` envirnoment variable.
    """

    username = os.getenv("CHECKERBOARD_USERNAME", "checkerboard")
    """Expected username for HTTP Basic Authentication.

    Set with the ``CHECKERBOARD_USERNAME`` environment variable.
    """

    password = os.getenv("CHECKERBOARD_PASSWORD", "")
    """Expected password for HTTP Basic Authentication.

    Set with the ``CHECKERBOARD_PASSWORD`` environment variable.
    """
