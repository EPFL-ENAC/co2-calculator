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
        >>> perms = {"modules.headcount": ["view"]}
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
        if not isinstance(perm_set, list) or action not in perm_set:
            return False

        return True

    except (KeyError, TypeError, AttributeError):
        return False
