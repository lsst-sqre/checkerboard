"""Configuration definition."""

__all__ = ["Configuration"]

import os

from pydantic import Field
from safir.logging import LogLevel, Profile
from safir.pydantic import CamelCaseModel


class Configuration(CamelCaseModel):
    """Configuration for checkerboard."""

    name: str = Field(
        os.getenv("SAFIR_NAME", "checkerboard"),
        title="Application name",
        description=(
            "The application's name, which doubles as the root HTTP"
            " endpoint path.  Set with the ``SAFIR_NAME``"
            " environment variable."
        ),
    )

    profile: Profile = Field(
        Profile(os.getenv("SAFIR_PROFILE", "production")),
        title="Application run profile",
        description=(
            "The application profile: 'development' or 'production'."
            " Set with the ``SAFIR_PROFILE`` environment variable."
        ),
    )

    logger_name: str = Field(
        os.getenv("SAFIR_LOGGER", "checkerboard"),
        title="Application logger root name",
        description=(
            "The root name of the application's logger.  Set with the"
            " ``SAFIR_LOGGER`` application variable."
        ),
    )

    log_level: LogLevel = Field(
        LogLevel(os.getenv("SAFIR_LOG_LEVEL", "INFO")),
        title="Application logger log level",
        description=(
            "The log level of the application's logger.  Set with the"
            " ``SAFIR_LOG_LEVEL`` environment variable."
        ),
    )

    profile_field: str = Field(
        os.getenv("CHECKERBOARD_PROFILE_FIELD", "GitHub Username"),
        title="Slack custom profile field for GitHub username",
        description=(
            "Name of the Slack custom profile field containing the"
            " GitHub username.  Set with the ``CHECKERBOARD_PROFILE_FIELD``"
            " environment variable."
        ),
    )

    refresh_interval: int = Field(
        int(os.getenv("CHECKERBOARD_REFRESH_INTERVAL", "3600")),
        title="Refresh interval for Slack <-> GitHub mapping update",
        description=(
            "How frequently (in seconds) to refresh the Slack <-> GitHub"
            " mapping.  Set with the ``CHECKERBOARD_REFRESH_INTERVAL``"
            " environment variable."
        ),
    )

    slack_token: str = Field(
        os.getenv("CHECKERBOARD_SLACK_TOKEN", ""),
        title="Slack token used for queries",
        description=(
            "The Slack token to use for queries.  Must be a bot token with"
            " users:read and users.profile:read scopes.  Set with the"
            " ``CHECKERBOARD_SLACK_TOKEN`` environment variable."
        ),
    )

    username: str = Field(
        os.getenv("CHECKERBOARD_USERNAME", "checkerboard"),
        title="Username for HTTP Basic Authentication",
        description=(
            "Expected username for HTTP Basic Authentication.  Set with the"
            " ``CHECKERBOARD_USERNAME`` environment variable."
        ),
    )

    password: str = Field(
        os.getenv("CHECKERBOARD_PASSWORD", ""),
        title="Password for HTTP Basic Authentication",
        description=(
            "Expected password for HTTP Basic Authentication.  Set with the"
            " ``CHECKERBOARD_PASSWORD`` environment variable."
        ),
    )

    redis_password: str = Field(
        os.getenv("CHECKERBOARD_REDIS_PASSWORD", ""),
        title="Password for Checkerboard to authenticate to its Redis",
        description=(
            "Password for using Checkerboard's Redis.  Set with the"
            " ``CHECKERBOARD_REDIS_PASSWORD`` environment variable."
        ),
    )

    redis_url: str = Field(
        os.getenv("CHECKERBOARD_REDIS_URL", ""),
        title="URL for Checkerboard's Redis",
        description=(
            "URL for Checkerboard's Redis.  Set with the"
            " ``CHECKERBOARD_REDIS_PASSWORD`` environment variable."
        ),
    )
