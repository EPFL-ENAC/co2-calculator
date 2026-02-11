"""Authorization service with helper functions for policy-based data filtering.

This module provides helper functions for building policy inputs and implementing
context-injected services that use OPA pattern for data filtering.
"""

from app.core.logging import get_logger
from app.core.policy import query_policy
from app.models.user import User

logger = get_logger(__name__)


def _build_data_filter_input(user: User, resource_type: str, action: str) -> dict:
    """
    Build OPA input for data filtering policy evaluation.

    This helper function constructs the input dictionary needed for
    query_policy("authz/data/list", ...) or query_policy("authz/data/access", ...).

    Args:
        user: Current user
        resource_type: Type of resource
            (e.g., "headcount", "professional_travel", "equipment")
        action: Action being performed (e.g., "list", "read", "access")

    Returns:
        OPA input dictionary with user context and resource details

    Example:
        ```python
        input_data = _build_data_filter_input(user, "headcount", "list")
        decision = await query_policy("authz/data/list", input_data)
        filters = decision.get("filters", {})
        ```
    """
    input_data = {
        "user": {"id": user.id, "email": user.email, "roles": user.roles or []},
        "resource_type": resource_type,
        "action": action,
    }

    return input_data


def _build_resource_access_input(
    user: User, resource_type: str, resource: dict
) -> dict:
    """
    Build OPA input for resource access policy evaluation.

    This helper function constructs the input dictionary needed for
    query_policy("authz/data/access", ...) to check if a user can access
    a specific resource.

    Args:
        user: Current user
        resource_type: Type of resource (e.g., "headcount", "professional_travel")
        resource: Resource dictionary with fields like:
            - "id": Resource ID
            - "created_by": User ID who created the resource
            - "unit_id": Unit ID the resource belongs to
            - Other resource-specific fields

    Returns:
        OPA input dictionary with user context and resource details

    Example:
        ```python
        resource = {"id": 123, "created_by": "user-123", "unit_id": "12345"}
        input_data = _build_resource_access_input(user, "headcount", resource)
        decision = await query_policy("authz/data/access", input_data)
        if not decision.get("allow"):
            raise HTTPException(403, "Access denied")
        ```
    """
    input_data = {
        "user": {"id": user.id, "email": user.email, "roles": user.roles or []},
        "resource_type": resource_type,
        "action": "access",
        "resource": resource,
    }

    return input_data


async def get_data_filters(
    user: User, resource_type: str, action: str = "list"
) -> dict:
    """
    Get data filters for a user based on their role scope.

    This is a convenience function that builds the input, queries the policy,
    and returns the filters directly.

    Args:
        user: Current user
        resource_type: Type of resource (e.g., "headcount", "professional_travel")
        action: Action being performed (e.g., "list", "read", default: "list")

    Returns:
        Filter dictionary with structure:
        {
            "unit_ids": [...],  # Optional: list of unit IDs to filter by
            "user_id": "...",    # Optional: user ID to filter by
            "scope": "global" | "unit" | "own"  # Scope determined by policy
        }

    Example:
        ```python
        filters = await get_data_filters(user, "equipment", "list")
        # Use filters in repository query
        entries = await data_entry_repo.get_entries(db, filters=filters)
        ```
    """
    input_data = _build_data_filter_input(user, resource_type, action)

    decision = await query_policy("authz/data/list", input_data)
    logger.info(
        "Data filter policy evaluated",
        extra={
            "user_id": user.id,
            "resource_type": resource_type,
            "action": action,
            "decision": decision,
        },
    )

    if not decision.get("allow", False):
        logger.warning(
            "Data filter policy denied access",
            extra={
                "user_id": user.id,
                "resource_type": resource_type,
                "action": action,
                "reason": decision.get("reason", "Access denied"),
            },
        )
        # Return restrictive filters if access denied
        return {"user_id": user.id, "scope": "denied"}

    filters = decision.get("filters", {})
    return filters


async def check_resource_access(
    user: User, resource_type: str, resource: dict, action: str = "access"
) -> bool:
    """
    Check if a user can access/edit/delete a specific resource.

    This function uses the new "authz/resource/access" policy for resource-level
    access control with business logic rules (e.g., API trips read-only,
    ownership rules for standard users).

    Args:
        user: Current user
        resource_type: Type of resource (e.g., "headcount", "professional_travel")
        resource: Resource dictionary with fields like:
            - "id": Resource ID
            - "created_by": User ID who created the resource
            - "unit_id": Unit ID the resource belongs to
            - "provider": Provider source (for professional_travel)
        action: Action type (default: "access") - for logging/future use

    Returns:
        True if user can access the resource, False otherwise

    Example:
        ```python
        # Check if user can edit a professional travel record
        resource = {
            "id": 123,
            "created_by": "user-123",
            "unit_id": "12345",
            "provider": "manual",
        }
        if not await check_resource_access(user, "professional_travel", resource):
            raise HTTPException(403, "Access denied")
        ```
    """
    input_data = {
        "user": {"id": user.id, "email": user.email, "roles": user.roles or []},
        "resource_type": resource_type,
        "action": action,
        "resource": resource,
    }

    # Use new resource access policy for resource-level checks
    decision = await query_policy("authz/resource/access", input_data)
    logger.info(
        "Resource access policy evaluated",
        extra={
            "user_id": user.id,
            "resource_type": resource_type,
            "resource_id": resource.get("id"),
            "action": action,
            "decision": decision,
        },
    )

    return decision.get("allow", False)
