"""Handlers for the app's external root, ``/<app-name>/``."""

__all__ = ["get_index"]


from safir.metadata import Metadata, get_metadata

from checkerboard.handlers import routes


@routes.get("/")
async def get_index() -> dict[str, Metadata]:
    """GET /checkerboard/ (the app's external root).

    By convention, the root of the external API includes a field called
    ``_metadata`` that provides the same metadata as the internal root
    endpoint. Here, the metadata is namespace so that you can customize the
    root of your API. For example, consider listing key API URLs.

    This was a bad design choice, because we can't use a Pydantic model for it,
    since fields with initial underscores are excluded from the model.
    """
    return {
        "_metadata": get_metadata(
            package_name="checkerboard", application_name="checkerboard"
        )
    }
