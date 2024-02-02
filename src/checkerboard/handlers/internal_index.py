"""Handlers for the app's root, ``/``."""


from fastapi import APIRouter
from safir.metadata import Metadata, get_metadata

__all__ = ["router"]

router = APIRouter()


@router.get(
    "/",
    description=("Return metadata about the running application."),
    response_model=Metadata,
    response_model_exclude_none=True,
    summary="Application metadata",
)
async def get_internal_index() -> Metadata:
    return get_metadata(
        package_name="checkerboard", application_name="checkerboard"
    )
