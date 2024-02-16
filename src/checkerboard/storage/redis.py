"""Redis interaction layer.

This implements the Redis cache operations which, in turn, are used by the
mapping service to answer questions about the user maps.
"""


import redis.asyncio as redis
import structlog
from structlog.stdlib import BoundLogger

from ..util import stringify_item, stringify_list


class MappingCache:
    """Abstraction around Redis cache to hold Slack-to-GitHub user mappings.

    If the key is not in the Redis map, we've never asked about it.
    If it is in the Redis map, but its value is the empty string,
    we've asked Slack and gotten the answer that there is no value in
    the GitHub Username field.  The Slack storage layer uses this
    information to order its queries, so we can prioritize finding out
    about unknown users over rechecking users we know we have *an*
    answer (maybe stale) for.

    It is the responsibility of the service layer to treat a None from
    the get (meaning no key exists) and the empty string (meaning we
    asked and got a reply that the user isn't mapped) the same.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        *,
        logger: BoundLogger | None = None,
    ) -> None:
        self._redis_client = redis_client
        self.logger = logger or structlog.get_logger(__name__)

    async def aclose(self) -> None:
        """Shut down cleanly."""
        await self._redis_client.aclose()

    async def set(self, key: str, value: str) -> None:
        """Set a key to a particular value.

        Parameters
        ----------
           key : `str`
           value : `str`

        Notes
        -----
        Because we know we're using this to store a GitHub user name, which
        is not case-sensitive, we're going to coerce the stored value to
        lowercase before storing.
        """
        canonical_value = stringify_item(value).lower()
        await self._redis_client.set(key, canonical_value)

    async def get(self, key: str) -> str | None:
        """
        Retrieve the value associated with a key.

        Parameters
        ----------
        key: `str`

        Returns
        -------
        value: `str`|None

        Notes
        -----
        The value is coerced to lowercase, although it should have already
        been stored as lowercase.  Since we know it's a GitHub username,
        which is not case-sensitive, this is correct behavior.

        If the key does not exist in Redis, return None.
        """
        if await self._redis_client.exists(key):
            return stringify_item(await self._redis_client.get(key)).lower()
        return None

    async def get_all(self) -> dict[str, str]:
        """Get all the keys and their values as a dict.  Keys without values
        are ignored.

        Returns
        -------
        map: `dict[str,str]`
        """
        retval: dict[str, str] = {}
        keys = await self.keys()
        for key in keys:
            val = await self.get(key)
            if val:
                retval[key] = val
        return retval

    async def delete(self, key: str) -> None:
        """Delete a key.  Deleting a key that doesn't exist is not an error."""
        await self._redis_client.delete(key)

    async def keys(self) -> list[str]:
        """Get all non-empty keys in the redis cache."""
        return [
            x for x in stringify_list(await self._redis_client.keys()) if x
        ]
