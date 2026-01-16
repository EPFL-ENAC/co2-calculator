"""Custom exception classes for permission-based access control."""


class PermissionDeniedError(Exception):
    """
    Base exception for permission-related access denials.

    Attributes:
        required_permission: The permission path that was required
            (e.g., "modules.headcount")
        action: The action that was attempted (e.g., "view", "edit", "export")
        message: Human-readable error message describing the denial
    """

    def __init__(
        self,
        required_permission: str,
        action: str,
        message: str,
    ):
        """
        Initialize PermissionDeniedError.

        Args:
            required_permission: The permission path that was required
            action: The action that was attempted
            message: Human-readable error message
        """
        self.required_permission = required_permission
        self.action = action
        self.message = message
        super().__init__(self.message)


class InsufficientScopeError(PermissionDeniedError):
    """
    Exception raised when user has the required permission but insufficient scope.

    This occurs when a user has the permission but their scope (global/unit/own)
    doesn't allow access to the requested resource. For example, a user with
    unit scope trying to access data from a different unit.

    Attributes:
        required_permission: The permission path that was required
        action: The action that was attempted
        message: Human-readable error message describing the scope issue
        user_scope: The scope the user has (e.g., "unit", "own", "global")
        required_scope: The scope required for access (optional)
    """

    def __init__(
        self,
        required_permission: str,
        action: str,
        message: str,
        user_scope: str | None = None,
        required_scope: str | None = None,
    ):
        """
        Initialize InsufficientScopeError.

        Args:
            required_permission: The permission path that was required
            action: The action that was attempted
            message: Human-readable error message
            user_scope: The scope the user has (optional)
            required_scope: The scope required for access (optional)
        """
        super().__init__(required_permission, action, message)
        self.user_scope = user_scope
        self.required_scope = required_scope


class RecordAccessDeniedError(PermissionDeniedError):
    """
    Exception raised when user has permission but business rules deny record access.

    This occurs when a user has the required permission but specific business
    rules prevent access to a particular record. For example, API-synced trips
    that are read-only, or records that belong to a different organizational unit.

    Attributes:
        required_permission: The permission path that was required
        action: The action that was attempted
        message: Human-readable error message describing the record-level denial
        record_id: The ID of the record that was denied (optional)
        reason: Specific reason for the denial (optional)
    """

    def __init__(
        self,
        required_permission: str,
        action: str,
        message: str,
        record_id: str | int | None = None,
        reason: str | None = None,
    ):
        """
        Initialize RecordAccessDeniedError.

        Args:
            required_permission: The permission path that was required
            action: The action that was attempted
            message: Human-readable error message
            record_id: The ID of the record that was denied (optional)
            reason: Specific reason for the denial (optional)
        """
        super().__init__(required_permission, action, message)
        self.record_id = record_id
        self.reason = reason
