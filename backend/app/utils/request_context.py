"""Request context extraction utilities for audit trail.

Provides helper functions to extract IP address, route information,
and payload from FastAPI Request objects for audit logging.
"""

from typing import Optional

from fastapi import Request

from app.core.logging import get_logger

logger = get_logger(__name__)


def extract_ip_address(request: Request) -> str:
    """
    Extract client IP address from request.

    Prioritizes X-Forwarded-For header (for proxy/load balancer scenarios)
    then falls back to direct client host.

    Args:
        request: FastAPI Request object

    Returns:
        IP address as string, or "unknown" if unavailable
    """
    # Check X-Forwarded-For header first (handles proxies/load balancers)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # X-Forwarded-For can contain multiple IPs (client, proxy1, proxy2, ...)
        # Take the first one (original client)
        return forwarded_for.split(",")[0].strip()

    # Fall back to direct client IP
    if request.client and request.client.host:
        return request.client.host

    logger.warning("Could not extract IP address from request")
    return "unknown"


async def extract_route_payload(request: Request) -> Optional[dict]:
    """
    Extract route payload from request.

    Combines query parameters and request body (if JSON) into a single dict.

    Args:
        request: FastAPI Request object

    Returns:
        Dict containing query params and/or body, or None if both are empty
    """
    payload = {}

    # Extract query parameters
    if request.query_params:
        payload["query"] = dict(request.query_params)

    # Extract body for POST/PUT/PATCH requests
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            # Check if content-type is JSON
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type.lower():
                body = await request.json()
                if body:
                    payload["body"] = body
        except Exception as e:
            # Body might already be consumed or not JSON
            logger.debug(f"Could not extract request body: {e}")

    return payload if payload else None


def extract_route_info(request: Request) -> tuple[str, Optional[dict]]:
    """
    Extract route path and basic info from request (synchronous version).

    Note: This does NOT extract the body. Use extract_route_payload for that.

    Args:
        request: FastAPI Request object

    Returns:
        Tuple of (route_path, query_params_dict)
    """
    route_path = request.url.path

    query_params = dict(request.query_params) if request.query_params else None

    return route_path, query_params
