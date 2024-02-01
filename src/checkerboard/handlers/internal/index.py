"""Handlers for the app's root, ``/``."""


from safir.metadata import Metadata, get_metadata

from checkerboard.handlers import internal_routes

__all__ = ["get_index"]


@internal_routes.get(
    "/",
    description=("Return metadata about the running application."),
    response_model=Metadata,
    response_model_exclude_none=True,
    summary="Application metadata",
)
async def get_index() -> Metadata:
    return get_metadata(
        package_name="checkerboard", application_name="checkerboard"
    )
