"""HTTP API route tables."""

from fastapi import APIRouter

__all__ = ["internal_routes", "routes"]


internal_routes = APIRouter()
"""Routes for the root application that serves from ``/``

Application-specific routes don't get attached here. In practice, only routes
for metrics and health checks get attached to this table. Attach public APIs
to ``routes`` instead since those are accessible from the public API gateway
and are prefixed with the application name.
"""

routes = APIRouter()
"""Routes for the public API that serves from ``/<api_name>/``."""
