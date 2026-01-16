"""Permission calculation utilities.

This module provides functions to calculate user permissions based on their roles.
Permissions are calculated dynamically from roles and returned as a structured dict.
"""

from typing import List, Optional

from app.models.user import GlobalScope, Role, RoleName, RoleScope


def calculate_user_permissions(roles: List[Role]) -> dict:
    """Calculate permissions based on user roles.

    This function maps role-based access control to permission-based access control.
    It processes all user roles and generates a comprehensive permissions structure.

    IMPORTANT: Backoffice roles and User roles are completely independent!
    - Backoffice roles ONLY grant backoffice.* permissions
    - User roles ONLY grant modules.* permissions
    - A person can have both types of roles, and permissions combine

    Permission Structure (flat with dot notation):
    {
        "backoffice.users": {"view": bool, "edit": bool, "export": bool},
        "modules.headcount": {"view": bool, "edit": bool},
        "modules.equipment": {"view": bool, "edit": bool},
        "modules.professional_travel": {"view": bool, "edit": bool},
        "modules.infrastructure": {"view": bool, "edit": bool},
        "modules.purchase": {"view": bool, "edit": bool},
        "modules.internal_services": {"view": bool, "edit": bool},
        "modules.external_cloud": {"view": bool, "edit": bool},
    }

    Backoffice Roles (affect backoffice.* ONLY):
    - CO2_BACKOFFICE_ADMIN: Full backoffice access (view/edit/export users)
    - CO2_BACKOFFICE_STD: View-only backoffice access

    User Roles (affect modules.* ONLY):
    - CO2_USER_PRINCIPAL: Full module access (view + edit)
    - CO2_USER_STD: View and edit access to professional_travel module
      (own trips only - enforced via resource-level policy)
    - CO2_USER_SECONDARY: View-only module access

    System Roles (affect system.* ONLY):
    - CO2_SERVICE_MGR: System route access only (reserved for future system routes)
      Note: Does NOT grant backoffice or module access. System routes are separate.

    Args:
        roles: List of Role objects containing role name and scope

    Returns:
        dict: Flat permissions object with dot-notation keys
    """
    if not roles:
        return {}

    # Initialize with all permissions set to False
    permissions = {
        "backoffice.users": {"view": False, "edit": False, "export": False},
        "backoffice.files": {"view": False},
        "system.users": {"edit": False},
        "modules.headcount": {"view": False, "edit": False},
        "modules.equipment": {"view": False, "edit": False},
        "modules.professional_travel": {"view": False, "edit": False},
        "modules.infrastructure": {"view": False, "edit": False},
        "modules.purchase": {"view": False, "edit": False},
        "modules.internal_services": {"view": False, "edit": False},
        "modules.external_cloud": {"view": False, "edit": False},
    }

    # Helper to check if scope is global (handles both GlobalScope objects and dicts)
    def is_global_scope(s):
        if isinstance(s, GlobalScope):
            return True
        if isinstance(s, dict):
            return s.get("scope") == "global"
        return False

    # Helper to check if scope is role scope (handles both RoleScope objects and dicts)
    def is_role_scope(s):
        if isinstance(s, RoleScope):
            return True
        if isinstance(s, dict):
            return "unit" in s or "affiliation" in s
        return False

    for role in roles:
        role_name = role.role if isinstance(role.role, str) else role.role.value
        scope = role.on

        # BACKOFFICE ROLES - Only affect backoffice.* permissions
        # Compare using enum value for consistency
        if role_name == RoleName.CO2_BACKOFFICE_ADMIN.value:
            if is_global_scope(scope):
                permissions["backoffice.users"] = {
                    "view": True,
                    "edit": True,
                    "export": True,
                }
                permissions["backoffice.files"]["view"] = True

        elif role_name == RoleName.CO2_BACKOFFICE_STD.value:
            # Backoffice std can have either global scope or affiliation scope
            # Both should grant view permission
            if is_global_scope(scope) or is_role_scope(scope):
                permissions["backoffice.users"]["view"] = True
                permissions["backoffice.files"]["view"] = True

        # USER ROLES - Only affect modules.* permissions
        elif role_name == RoleName.CO2_USER_PRINCIPAL.value:
            if is_role_scope(scope):
                permissions["modules.headcount"] = {"view": True, "edit": True}
                permissions["modules.equipment"] = {"view": True, "edit": True}
                permissions["modules.professional_travel"] = {
                    "view": True,
                    "edit": True,
                }
                permissions["modules.infrastructure"] = {"view": True, "edit": True}
                permissions["modules.purchase"] = {"view": True, "edit": True}
                permissions["modules.internal_services"] = {"view": True, "edit": True}
                permissions["modules.external_cloud"] = {"view": True, "edit": True}

        elif role_name == RoleName.CO2_USER_STD.value:
            if is_role_scope(scope):
                permissions["modules.professional_travel"]["view"] = True
                permissions["modules.professional_travel"]["edit"] = True

        elif role_name == RoleName.CO2_USER_SECONDARY.value:
            if is_role_scope(scope):
                permissions["modules.headcount"] = {"view": True, "edit": True}
                permissions["modules.equipment"] = {"view": True, "edit": True}
                permissions["modules.professional_travel"] = {
                    "view": True,
                    "edit": True,
                }
                permissions["modules.infrastructure"] = {"view": True, "edit": True}
                permissions["modules.purchase"] = {"view": True, "edit": True}
                permissions["modules.internal_services"] = {"view": True, "edit": True}
                permissions["modules.external_cloud"] = {"view": True, "edit": True}

        # SYSTEM ROLE - Only affects system.* permissions
        elif role_name == RoleName.CO2_SERVICE_MGR.value:
            if is_global_scope(scope):
                permissions["system.users"]["edit"] = True

    return permissions


def has_permission(
    permissions: Optional[dict], path: str, action: str = "view"
) -> bool:
    """Check if a specific permission exists and is True.

    This is a helper function for checking permissions in application code.
    Works with flat permission structure using dot-notation keys.

    Args:
        permissions: The permissions dict (from user.permissions)
        path: Dot-notation path (e.g., "modules.headcount")
        action: The action to check (e.g., "view", "edit", "export")

    Returns:
        bool: True if the permission exists and is True, False otherwise

    Examples:
        >>> perms = {"modules.headcount": {"view": True, "edit": False}}
        >>> has_permission(perms, "modules.headcount", "view")
        True
        >>> has_permission(perms, "modules.headcount", "edit")
        False
        >>> has_permission(perms, "modules.equipment", "view")
        False
    """
    if not permissions:
        return False

    try:
        # Look up the path directly (flat structure)
        if path not in permissions:
            return False

        perm_set = permissions[path]

        # Check the action
        if not isinstance(perm_set, dict) or action not in perm_set:
            return False

        return bool(perm_set[action])

    except (KeyError, TypeError, AttributeError):
        return False


def get_permission_value(permissions: Optional[dict], full_path: str) -> Optional[bool]:
    """Get the value of a specific permission using full dot-notation path.

    Args:
        permissions: The permissions dict (from user.permissions)
        full_path: Full dot-notation path including action

    Returns:
        Optional[bool]: The permission value, or None if not found

    Examples:
        >>> perms = {"modules.headcount": {"view": True, "edit": False}}
        >>> get_permission_value(perms, "modules.headcount.view")
        True
        >>> get_permission_value(perms, "modules.headcount.edit")
        False
        >>> get_permission_value(perms, "modules.equipment.view")
        None
    """
    if not permissions:
        return None

    try:
        # Split into resource path and action
        # e.g., "modules.headcount.view" -> ["modules.headcount", "view"]
        parts = full_path.rsplit(".", 1)
        if len(parts) != 2:
            return None

        resource_path, action = parts

        # Look up in flat structure
        if resource_path not in permissions:
            return None

        perm_set = permissions[resource_path]
        if not isinstance(perm_set, dict) or action not in perm_set:
            return None

        return bool(perm_set[action])

    except (KeyError, TypeError, AttributeError, ValueError):
        return None
