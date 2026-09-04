"""Public errors must never reveal invitation or storage details."""

from fastapi import HTTPException, status


def invalid_invitation() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Interview link is unavailable or has expired.",
    )
