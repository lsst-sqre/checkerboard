"""Simple HTTP Basic authentication implementation."""

import secrets
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from ..exceptions import AuthenticationError
from .config import config_dependency

__all__ = ["auth_dependency"]

security = HTTPBasic()


def auth_dependency(
    credentials: Annotated[HTTPBasicCredentials, Depends(security)],
) -> None:
    """Check for correct username and password."""
    config = config_dependency.config()
    request_username = credentials.username.encode()
    correct_username = config.username.encode()
    request_password = credentials.password.encode()
    correct_password = config.password.encode()
    is_correct_username = secrets.compare_digest(
        request_username, correct_username
    )
    is_correct_password = secrets.compare_digest(
        request_password, correct_password
    )
    if not (is_correct_username and is_correct_password):
        raise AuthenticationError("Username and/or password incorrect")
