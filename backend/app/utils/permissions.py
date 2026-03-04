"""Permission calculation utilities.

This module provides functions to calculate user permissions based on their roles.
Permissions are calculated dynamically from roles and returned as a structured dict.
"""

from typing import Optional


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
