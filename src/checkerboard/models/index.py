"""Top-level request model for Checkerboard."""

from pydantic import BaseModel, Field
from safir.metadata import Metadata

__all__ = ["Index"]


class Index(BaseModel):
    """Metadata returned by the external root URL of the application.

    Notes
    -----
    As written, this is not very useful. Add additional metadata that will be
    helpful for a user exploring the application, or replace this model with
    some other model that makes more sense to return from the application API
    root.
    """

    _metadata: Metadata = Field(..., title="Package metadata")
