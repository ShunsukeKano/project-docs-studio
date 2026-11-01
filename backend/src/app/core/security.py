"""HTTP Basic authentication for the writer API (a single shared login)."""

import base64
import binascii
import secrets

from fastapi import Request

from app.core.config import Settings
from app.core.errors import UnauthorizedError


def _parse_basic_header(value: str | None) -> tuple[bytes, bytes] | None:
    """Return (user, password) as UTF-8 bytes, or None when the header is absent or malformed."""
    if not value:
        return None
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "basic" or not token:
        return None
    try:
        decoded = base64.b64decode(token.strip(), validate=True)
    except (binascii.Error, ValueError):
        return None
    user, separator, password = decoded.partition(b":")
    if not separator:
        return None
    return user, password


async def require_basic_auth(request: Request) -> None:
    settings: Settings = request.app.state.settings
    if not settings.basic_auth_enabled:
        return

    supplied = _parse_basic_header(request.headers.get("authorization"))
    expected_user = settings.basic_auth_user.encode("utf-8")
    expected_password = settings.basic_auth_password.get_secret_value().encode("utf-8")
    supplied_user, supplied_password = supplied if supplied else (b"", b"")

    # Both fields are always compared, so the time taken does not reveal which one was wrong.
    user_ok = secrets.compare_digest(supplied_user, expected_user)
    password_ok = secrets.compare_digest(supplied_password, expected_password)
    if supplied is None or not (user_ok and password_ok):
        raise UnauthorizedError()
