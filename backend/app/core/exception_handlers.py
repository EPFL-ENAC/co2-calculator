"""Exception handlers for custom exceptions."""

from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    InsufficientScopeError,
    PermissionDeniedError,
    RecordAccessDeniedError,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


async def permission_denied_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Handle PermissionDeniedError and its subclasses.

    Returns HTTP 403 with a clear, structured error message that includes:
    - The required permission path and action
    - A human-readable message
    - Additional context for specific error types

    Args:
        request: The FastAPI request object
        exc: The exception instance (must be PermissionDeniedError or subclass)

    Returns:
        JSONResponse with status 403 and error details
    """
    # Type check: ensure this is a PermissionDeniedError
    if not isinstance(exc, PermissionDeniedError):
        # Fallback for unexpected exception types
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": "Permission denied"},
        )

    # Build the permission string (e.g., "modules.headcount.view")
    permission_string = f"{exc.required_permission}.{exc.action}"

    # Build the error detail message
    detail = f"Permission denied: {exc.message}"

    # Log the permission denial
    logger.warning(
        "Permission denied",
        extra={
            "required_permission": exc.required_permission,
            "action": exc.action,
            "permission_string": permission_string,
            "message": exc.message,
            "exception_type": type(exc).__name__,
            "path": request.url.path,
            "method": request.method,
        },
    )

    # Build response content
    content: dict[str, Any] = {
        "detail": detail,
        "permission": {
            "path": exc.required_permission,
            "action": exc.action,
            "required": permission_string,
        },
    }

    # Add type-specific context
    if isinstance(exc, InsufficientScopeError):
        content["scope"] = {}
        if exc.user_scope:
            content["scope"]["user_scope"] = exc.user_scope
        if exc.required_scope:
            content["scope"]["required_scope"] = exc.required_scope

    if isinstance(exc, RecordAccessDeniedError):
        content["record"] = {}
        if exc.record_id is not None:
            content["record"]["id"] = str(exc.record_id)
        if exc.reason:
            content["record"]["reason"] = exc.reason

    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content=content,
    )
