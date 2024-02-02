"""Config dependency for FastAPI."""

from safir.logging import configure_logging

from ..config import Configuration

__all__ = ["ConfigDependency", "config_dependency"]


class ConfigDependency:
    """Provides the configuration as a dependency.

    We don't use a configuration file; it's driven entirely through the
    environment.  Thus there's really no way to change the configuration
    and reload as such, since the environment variables are read at
    startup when the configuration is created.
    """

    def __init__(self) -> None:
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
