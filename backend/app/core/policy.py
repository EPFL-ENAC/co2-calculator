"""Policy evaluation module for authorization decisions."""

from typing import Any, Optional

from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.role_priority import pick_role_for_institutional_id
from app.models.module_type import ModuleTypeEnum
from app.models.unit import Unit
from app.models.user import (
    GlobalScope,
    Role,
    RoleName,
    RoleScope,
    User,
    calculate_user_permissions,
)
from app.utils.permissions import has_permission

logger = get_logger(__name__)


async def _evaluate_permission_policy(input_data: dict) -> dict:
    """
    Evaluate permission check policy.

    Args:
        input_data: Dictionary containing:
            - "user": User object or dict with user info
            - "path": Permission path (e.g., "modules.headcount")
            - "action": Permission action (e.g., "view", "edit", default: "view")
            - "institutional_id": Optional unit institutional_id for scoped lookup
              of ``modules.*`` paths (e.g., ``"modules.headcount/0184"``).
            - "any_scope": Optional bool. Taxonomy-only escape hatch; see
              ``has_permission``.

    Returns:
        Policy decision dict: {"allow": bool, "reason": str}
    """
    user_data = input_data.get("user")
    path = input_data.get("path")
    action = input_data.get("action", "view")
    institutional_id = input_data.get("institutional_id")
    any_scope = input_data.get("any_scope", False)

    if not user_data or not path:
        logger.warning(
            "Permission check failed: missing user or path",
            extra={"input_data": input_data},
        )
        return {
            "allow": False,
            "reason": "Missing user or permission path",
        }

    # Handle User object
    if isinstance(user_data, User):
        permissions = user_data.calculate_permissions()
    # Handle dict with permissions already calculated
    elif isinstance(user_data, dict) and "permissions" in user_data:
        permissions = user_data["permissions"]
    # Handle dict with roles (calculate permissions)
    elif isinstance(user_data, dict) and "roles" in user_data:
        # Convert role dicts to Role objects if needed
        roles_data = user_data["roles"]
        roles = [
            Role(**r) if isinstance(r, dict) else r for r in roles_data if r is not None
        ]
        permissions = calculate_user_permissions(roles)
    else:
        logger.warning(
            "Permission check failed: invalid user data format",
            extra={"user_data_type": type(user_data).__name__},
        )
        return {
            "allow": False,
            "reason": "Invalid user data format",
        }

    # Check permission using existing utility
    if has_permission(
        permissions,
        path,
        action,
        institutional_id=institutional_id,
        any_scope=any_scope,
    ):
        logger.info(
            "Permission granted",
            extra={
                "path": path,
                "action": action,
                "user_id": user_data.id
                if isinstance(user_data, User)
                else user_data.get("id"),
            },
        )
        return {
            "allow": True,
            "reason": f"Permission granted: {path}.{action}",
        }

    logger.warning(
        "Permission denied",
        extra={
            "path": path,
            "action": action,
            "user_id": user_data.id
            if isinstance(user_data, User)
            else user_data.get("id"),
        },
    )
    return {
        "allow": False,
        "reason": f"Permission denied: {path}.{action} required",
    }


async def _evaluate_resource_access_policy(input_data: dict) -> dict:
    """
    Evaluate resource-level access policy for specific resources.

    Checks if a user can access/edit a specific resource based on:
    - Resource type and properties (e.g., provider, created_by)
    - User roles and scope
    - Business logic rules

    Args:
        input_data: Dictionary containing:
            - "user": User object or dict with user info (must have roles)
            - "resource_type": Resource type (e.g., "professional_travel")
            - "resource": Resource dict with properties like:
                - "id": Resource ID
                - "created_by": User ID who created the resource
                - "unit_id": Unit ID the resource belongs to
                - "provider": Provider source (for professional_travel)

    Returns:
        Policy decision dict: {"allow": bool, "reason": str}
    """
    user_data = input_data.get("user")
    resource_type = input_data.get("resource_type", "")
    resource = input_data.get("resource", {})

    if not user_data:
        return {"allow": False, "reason": "Missing user"}

    if not resource:
        return {"allow": False, "reason": "Missing resource"}

    # Extract roles and user_id
    user_id: int | None = None
    if isinstance(user_data, User):
        roles = user_data.roles or []
        user_id = user_data.id
    elif isinstance(user_data, dict):
        roles_data = user_data.get("roles", [])
        roles = [
            Role(**r) if isinstance(r, dict) else r for r in roles_data if r is not None
        ]
        id_value = user_data.get("id")
        user_id = id_value if isinstance(id_value, int) else None
    else:
        return {"allow": False, "reason": "Invalid user data format"}

    # Professional Travel resource access rules
    if resource_type == "professional_travel":
        provider = resource.get("provider", "")
        created_by = resource.get("created_by", "")
        resource_unit_id = resource.get("unit_id", "")

        # Rule 1: API trips are read-only (cannot be edited by anyone)
        if provider == "api":
            return {
                "allow": False,
                "reason": "API trips are read-only and cannot be edited",
            }

        # Rule 2: Check if user has global scope (backoffice admin)
        has_global_scope = any(
            isinstance(role.on, GlobalScope)
            or (isinstance(role.on, dict) and role.on.get("scope") == "global")
            for role in roles
        )
        if has_global_scope:
            return {"allow": True, "reason": "Global scope access (backoffice admin)"}

        # Rule 3: Check if user has unit scope for this resource's unit
        user_unit_ids = set()
        principal_or_secondary = False
        for role in roles:
            role_name = role.role if isinstance(role.role, str) else role.role.value
            role_scope = role.on

            # Check if principal role
            if role_name == RoleName.CO2_USER_PRINCIPAL.value:
                principal_or_secondary = True
                # Extract unit from scope
                if isinstance(role_scope, RoleScope) and role_scope.institutional_id:
                    user_unit_ids.add(role_scope.institutional_id)
                elif isinstance(role_scope, dict) and role_scope.get(
                    "institutional_id"
                ):
                    user_unit_ids.add(role_scope["institutional_id"])

        # Principals can edit manual/CSV trips in their units
        if principal_or_secondary and resource_unit_id in user_unit_ids:
            return {
                "allow": True,
                "reason": (
                    "Unit scope access (principal can edit trips in their units)"
                ),
            }

        # Rule 4: Standard users can only edit their own manual trips
        if user_id and created_by == user_id:
            return {
                "allow": True,
                "reason": "Owner access (user can edit their own trips)",
            }

        # Default: deny access
        return {
            "allow": False,
            "reason": "Insufficient permissions to access this resource",
        }

    # Default for other/unhandled resource types: deny by default
    # This ensures new resource types are secure until explicit policy rules are added
    logger.warning(
        "Resource access denied: no policy defined for resource type",
        extra={"resource_type": resource_type},
    )
    return {
        "allow": False,
        "reason": "No policy defined for resource type",
    }


async def _evaluate_data_filter_policy(input_data: dict) -> dict:
    """
    Evaluate data filtering policy based on user's role scope.

    Determines filter criteria based on user's roles:
    - Global scope (backoffice admin): No filters (can see all)
    - Unit scope (principal/secondary): Filter by unit_ids from roles
    - Own scope (standard user): Filter by user_id

    Args:
        input_data: Dictionary containing:
            - "user": User object or dict with user info (must have roles)
            - "resource_type": Resource type (e.g., "headcount", "professional_travel")
            - "action": Action (e.g., "list", "read", "access")

    Returns:
        Policy decision dict: {
            "allow": bool,
            "filters": {"unit_ids": [...], "user_id": ...}
        }
    """
    user_data = input_data.get("user")
    resource_type = input_data.get("resource_type", "")
    action = input_data.get("action", "list")

    if not user_data:
        logger.warning(
            "Data filter check failed: missing user",
            extra={"input_data": input_data},
        )
        return {
            "allow": False,
            "reason": "Missing user",
            "filters": {},
        }

    # Extract roles from user data
    user_id: int | None = None
    if isinstance(user_data, User):
        roles = user_data.roles or []
        user_id = user_data.id
    elif isinstance(user_data, dict):
        roles_data = user_data.get("roles", [])
        # Convert role dicts to Role objects if needed
        roles = [
            Role(**r) if isinstance(r, dict) else r for r in roles_data if r is not None
        ]
        # Extract user_id from dict, ensuring it's int | None
        id_value = user_data.get("id")
        user_id = id_value if isinstance(id_value, int) else None
    else:
        logger.warning(
            "Data filter check failed: invalid user data format",
            extra={"user_data_type": type(user_data).__name__},
        )
        return {
            "allow": False,
            "reason": "Invalid user data format",
            "filters": {},
        }

    # Determine scope and build filters
    filters: dict[str, Any] = {}
    scope = "own"  # Default scope

    # Check for global scope (backoffice admin)
    has_global_scope = any(
        isinstance(role.on, GlobalScope)
        or (isinstance(role.on, dict) and role.on.get("scope") == "global")
        for role in roles
    )

    if has_global_scope:
        # Global scope: no filters (can see all)
        scope = "global"
        filters = {}  # Empty filters = no restrictions
        logger.info(
            "Data filter: global scope",
            extra={
                "user_id": user_id,
                "resource_type": resource_type,
                "action": action,
                "scope": scope,
            },
        )
    else:
        # Collect unit IDs from unit-scoped roles
        unit_ids = set()
        for role in roles:
            role_scope = role.on
            # Handle RoleScope objects
            if isinstance(role_scope, RoleScope) and role_scope.institutional_id:
                unit_ids.add(role_scope.institutional_id)
            # Handle dict format
            elif isinstance(role_scope, dict) and role_scope.get("institutional_id"):
                unit_ids.add(role_scope["institutional_id"])
        if unit_ids:
            # Unit scope: filter by unit_ids
            scope = "unit"
            filters = {"unit_ids": list(unit_ids)}
            logger.info(
                "Data filter: unit scope",
                extra={
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "action": action,
                    "scope": scope,
                    "unit_ids": list(unit_ids),
                },
            )
        elif user_id:
            # Own scope: filter by user_id (standard users see only their own data)
            scope = "own"
            filters = {"user_id": user_id}
            logger.info(
                "Data filter: own scope",
                extra={
                    "user_id": user_id,
                    "resource_type": resource_type,
                    "action": action,
                    "scope": scope,
                },
            )

    # Add scope to filters for logging/debugging
    filters["scope"] = scope

    return {
        "allow": True,
        "reason": f"Data filter applied: {scope} scope",
        "filters": filters,
    }


async def query_policy(policy_name: str, input_data: dict) -> dict:
    """
    Query policy engine for authorization decisions.

    Supports multiple policy types:
    - "authz/permission/check": Permission-based authorization
    - "authz/resource/list": Resource listing with filters
    - "authz/resource/read": Resource access check
    - "authz/resource/access": Resource-level access for edit/delete operations
    - "authz/unit/list": Unit listing with filters
    - "authz/data/list": Data filtering based on user scope
    - "authz/data/access": Data access filtering for single resource

    Args:
        policy_name: Policy path to evaluate (e.g., "authz/permission/check")
        input_data: Policy input data (user context, resource info, etc.)

    Returns:
        Policy decision dict with structure:
        {
            "allow": bool,
            "reason": str,
            "filters": dict (optional, for data filtering policies)
        }
    """
    # Route to appropriate policy evaluator
    if policy_name == "authz/permission/check":
        return await _evaluate_permission_policy(input_data)

    if policy_name == "authz/resource/access":
        return await _evaluate_resource_access_policy(input_data)

    if policy_name in ("authz/data/list", "authz/data/access"):
        return await _evaluate_data_filter_policy(input_data)

    # Legacy/fallback: For resource and unit policies, return basic allow
    # These can be extended later with proper policy evaluation
    filters = input_data.get("filters", None)
    return {
        "allow": True if filters is not None else True,  # Default allow for now
        "reason": "Filtered query" if filters else "Policy evaluation",
        "filters": filters or {},
    }


def _get_module_permission_path(module_name: str | None) -> Optional[str]:
    """
    Map module name to permission path.

    Args:
        module_name: Module name (e.g., "professional-travel")
            (e.g., "professional-travel", "equipment-electric-consumption")

    Returns:
        Permission path (e.g., "modules.professional_travel") or None
        if module doesn't require permission
    """
    if module_name is None or module_name.strip() == "":
        return None  # No module specified, no permission required
    # Name mapping for modules with legacy permission paths
    module_permission_map = {
        "equipment_electric_consumption": "modules.equipment",
        "my_lab": "modules.headcount",  # Headcount module
    }
    normalized_name = module_name.replace("-", "_").lower().strip()
    return module_permission_map.get(normalized_name, f"modules.{normalized_name}")


async def get_module_permission_decision(
    user: User,
    module_id: str | int,
    action: str = "view",
    *,
    institutional_id: Optional[str] = None,
    any_scope: bool = False,
) -> dict:
    """
    Get permission decision for a specific module and action.

    Args:
        user: Current user
        module_id: Module enum identifier or name
        action: Permission action (e.g., "view", "edit", "export", default: "view")
        institutional_id: Unit institutional_id for scoped permission lookup.
            Routes that operate on a unit MUST pass this — without it, scoped
            users (CO2_USER_*) will be denied because their permissions are
            stored as ``modules.X/{institutional_id}``.
        any_scope: Taxonomy-only escape hatch. See ``has_permission``.

    Returns:
        OPA decision dictionary, e.g. {"allow": True}
          or {"allow": False, "reason": "User does not have required role"}
    """
    module_name = (
        module_id if isinstance(module_id, str) else ModuleTypeEnum(module_id).name
    )
    permission_path = _get_module_permission_path(module_name)
    if not permission_path:
        # Module doesn't require permission check, allow access
        return {"allow": True, "reason": "No permission required for this module"}

    input_data = {
        "user": {
            "id": user.id,
            "email": user.email,
            "roles": user.roles or [],
        },
        "path": permission_path,
        "action": action,
        "institutional_id": institutional_id,
        "any_scope": any_scope,
    }
    return await query_policy("authz/permission/check", input_data)


async def is_module_permitted(
    user: User,
    module_id: str | int,
    action: str = "view",
    *,
    institutional_id: Optional[str] = None,
    any_scope: bool = False,
) -> bool:
    """
    Check if user has permission for a specific module and action.

    Args:
        user: Current user
        module_id: Module enum identifier or name
        action: Permission action (e.g., "view", "edit", default: "view")
        institutional_id: Unit institutional_id for scoped permission lookup.
        any_scope: Taxonomy-only escape hatch. See ``has_permission``.

    Returns:
        True if user has permission, False otherwise
    """
    decision = await get_module_permission_decision(
        user,
        module_id,
        action,
        institutional_id=institutional_id,
        any_scope=any_scope,
    )
    return decision.get(
        "allow", False
    )  # Deny by default if decision lacks an explicit allow


async def check_module_permission(
    user: User,
    module_id: str | int,
    action: str,
    *,
    institutional_id: Optional[str] = None,
    any_scope: bool = False,
) -> None:
    """
    Check if user has permission for the module.

    Args:
        user: Current user.
        module_id: Module enum identifier or name.
        action: Permission action ("view" or "edit").
        institutional_id: Unit institutional_id for scoped permission lookup.
            Routes that operate on a unit MUST pass this.
        any_scope: Taxonomy-only escape hatch. See ``has_permission``.

    Raises:
        HTTPException: 403 if permission denied.
    """
    module_name = (
        module_id if isinstance(module_id, str) else ModuleTypeEnum(module_id).name
    )
    permission_path = _get_module_permission_path(module_name) or "unknown_module"
    decision = await get_module_permission_decision(
        user,
        module_id,
        action,
        institutional_id=institutional_id,
        any_scope=any_scope,
    )

    logger.info(
        "Module permission check",
        extra={
            "user_id": sanitize(user.id),
            "module_id": sanitize(module_id),
            "permission_path": sanitize(permission_path),
            "action": action,
            "decision": decision,
        },
    )

    if not decision.get("allow", False):
        reason = decision.get("reason", "Permission denied")
        logger.warning(
            "Module permission check denied",
            extra={
                "user_id": sanitize(user.id),
                "module_id": sanitize(module_id),
                "permission_path": sanitize(permission_path),
                "action": action,
                "reason": reason,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {reason}",
        )


def require_unit_access(current_user: User, unit: Unit | None) -> None:
    """Raise 403/404 unless the user has global or unit-scoped access.

    Enforcer counterpart to ``check_module_permission`` for the unit data
    boundary. Keeps the role-walking logic in one place so simulator and
    calculator endpoints stay in lockstep.

    Allows:
    - Global-scope roles (backoffice / superadmin).
    - Any role (PRINCIPAL or STD) scoped to the unit's ``institutional_id``
      via ``pick_role_for_institutional_id``.

    Args:
        current_user: The authenticated user.
        unit: The loaded Unit ORM object, or None if the unit was not found.

    Raises:
        HTTPException 404: If ``unit`` is None.
        HTTPException 403: If the user has no qualifying role for the unit.
    """
    if any(isinstance(role.on, GlobalScope) for role in current_user.roles):
        return
    if unit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Unit not found",
        )
    if (
        unit.institutional_id is None
        or pick_role_for_institutional_id(current_user.roles, unit.institutional_id)
        is None
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access to this unit is not permitted.",
        )


async def check_module_permission_for_unit(
    *,
    current_user: User,
    module_id: str,
    action: str,
    db: AsyncSession,
    unit_id: int,
) -> Unit:
    """Load the Unit and gate access using its ``institutional_id``.

    Module permissions are stored as ``modules.{name}/{institutional_id}`` (see
    PR #974). Routes that operate on a specific unit must look up the unit's
    ``institutional_id`` before delegating to the policy — otherwise scoped
    users (CO2_USER_*) are denied because the bare-path lookup misses.

    Returns the loaded ``Unit`` so callers can reuse it (e.g. for travel filters
    or principal/global checks) without re-fetching.
    """
    unit = await db.get(Unit, unit_id)
    if unit is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unit {unit_id} not found",
        )
    await check_module_permission(
        current_user,
        module_id,
        action,
        institutional_id=unit.institutional_id,
    )
    return unit
