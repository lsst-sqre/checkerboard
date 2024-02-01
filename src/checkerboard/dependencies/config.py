"""Config dependency for FastAPI."""

from __future__ import annotations

import os
from pathlib import Path

from safir.logging import configure_logging

from ..config import Configuration
from ..constants import CONFIG_PATH

__all__ = ["ConfigDependency", "config_dependency"]


class ConfigDependency:
    """Provides the configuration as a dependency.

    We want a production deployment to default to one configuration path, but
    allow that path to be overridden by the test suite and, if the path
    changes, to reload the configuration (which allows sharing the same set of
    global singletons across multiple tests).  Do this by loading the config
    dynamically when it's first requested and reloading it whenever the
    configuration path is changed.
    """

    def __init__(self) -> None:
        config_path = os.getenv("CHECKERBOARD_CONFIG_PATH", CONFIG_PATH)
        self._config_path = Path(config_path)
        self._config: Configuration | None = None

    async def __call__(self) -> Configuration:
        """Load the configuration if necessary and return it."""
        return self.config()

    def config(self) -> Configuration:
        """Load the configuration if necessary and return it.

        This is equivalent to using the dependency as a callable except that
        it's not async and can therefore be used from non-async functions.
        """
        if not self._config:
            self._config = Configuration()  # Sets values from environment
            configure_logging(
                profile=self._config.profile,
                log_level=self._config.log_level,
                name=self._config.logger_name,
            )
        return self._config


config_dependency = ConfigDependency()
"""The dependency that will return the current configuration."""
