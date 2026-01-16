"""Unit service for business logic with Policy integration."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlalchemy.sql import Select
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import query_policy
from app.core.role_priority import role_priority_case
from app.models.unit import Unit
from app.models.unit_user import UnitUser
from app.models.user import User
from app.repositories.unit_repo import UnitRepository
from app.repositories.unit_user_repo import UnitUserRepository

logger = get_logger(__name__)


class UnitService:
    """Service for unit business logic and orchestration."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.unit_repo = UnitRepository(session)
        self.unit_user_repo = UnitUserRepository(session)

    def _build_policy_input(
        self, user: User, action: str, unit: Optional[Unit] = None
    ) -> dict:
        """
        Build OPA input data from user and unit context.

        Args:
            user: Current user
            action: Action to authorize (read, create, update, delete)
            unit: Optional unit being accessed

        Returns:
            input dictionary for policy engine
        """
        input_data = {
            "action": action,
            "resource_type": "unit",
            "user": {"id": user.id, "email": user.email, "roles": user.roles or []},
        }

        if unit:
            input_data["resource"] = {
                "id": unit.id,
                "created_by": unit.created_by,
                "visibility": unit.visibility,
            }

        return input_data

    async def get_user_units(
        self, user: User, skip: int = 0, limit: int = 100
    ) -> List[dict]:
        """
        List units with policy authorization and enriched user data.

        This orchestrates:
        1. Policy authorization with user context
        2. Querying units with filters from policy
        3. Enriching with user-specific role information
        4. Joining with principal user details

        Returns:
            List of dicts with structure:
            {
                "id": "12345",
                "name": "ENAC-IT4R",
                "current_user_role": "calco2.user.principal",
                "principal_user_id": "67890",
                "principal_user_name": "Alice",
                "principal_user_function": "Professor",
                "affiliations": ["ENAC", "ENAC-IT"],
                "visibility": "private"
            }
        """
        # 1. Build policy input
        input_data = self._build_policy_input(user, "read")

        # 2. Query policy for authorization decision
        decision = await query_policy("authz/unit/list", input_data)
        logger.info(
            "Policy decision requested",
            extra={
                "user_id": sanitize(user.id),
                "action": "list_user_units",
                "decision": sanitize(decision),
                "input_data": sanitize(input_data),
            },
        )

        # TBD: Implement deny logic
        # if not decision.get("allow", False):
        #     reason = decision.get("reason", "Access denied")
        #     logger.warning(
        #         "Policy denied list", extra={"user_id": user.id, "reason": reason}
        #     )
        #     raise HTTPException(status_code=403, detail=f"Access denied: {reason}")

        # 3. Extract filters from policy decision
        filters = decision.get("filters", {})

        # 4. Build complex query with joins (service-level orchestration)
        query: Select = (
            select(
                Unit,
                UnitUser.role,
                col(User.display_name).label("principal_user_name"),
            )
            .select_from(Unit)  # explicitly start from Unit
            .join(UnitUser, UnitUser.unit_id == Unit.id)  # type: ignore
            .outerjoin(User, Unit.principal_user_id == User.id)  # type: ignore
            .where(UnitUser.user_id == user.id)
        )

        # Apply filters from policy engine
        if "unit_id" in filters:
            unit_ids = filters["unit_id"]
            if isinstance(unit_ids, list):
                query = query.where(col(Unit.id).in_(unit_ids))
            else:
                query = query.where(Unit.id == unit_ids)
        if "visibility" in filters:
            visibilities = filters["visibility"]
            if isinstance(visibilities, list):
                query = query.where(col(Unit.visibility).in_(visibilities))
            else:
                query = query.where(Unit.visibility == visibilities)

        role_case = role_priority_case(UnitUser.role)
        query = query.order_by(role_case).offset(skip).limit(limit)

        result = await self.session.execute(query)
        rows = result.all()

        # Convert to dict format
        return [
            {
                "id": unit.id,  # unit, pas row
                "name": unit.name,
                "current_user_role": role,  # role, pas row.current_user_role
                "principal_user_id": unit.principal_user_id,
                "principal_user_name": principal_user_name,
                "principal_user_function": unit.principal_user_function,
                "affiliations": unit.affiliations or [],
                "visibility": unit.visibility,
            }
            for unit, role, principal_user_name in rows
        ]

    async def get_by_id(self, unit_id: str, user: User) -> Unit:
        """
        Get a unit by ID with authorization.

        Args:
            unit_id: Unit ID
            user: Current user

        Returns:
            Unit if authorized

        Raises:
            HTTPException: If resource not found or access denied
        """
        # Get unit from repository
        unit = await self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found"
            )

        # Build policy input with unit context
        input_data = self._build_policy_input(user, "read", unit)

        # Query policy for authorization
        decision = await query_policy("authz/resource/read", input_data)
        logger.info(
            "Policy read decision requested",
            extra={
                "user_id": user.id,
                "action": "get_unit",
                "unit_id": sanitize(unit_id),
            },
        )

        if not decision.get("allow", False):
            reason = decision.get("reason", "Access denied")
            logger.warning(
                "OPA denied resource read",
                extra={
                    "user_id": sanitize(user.id),
                    "unit_id": sanitize(unit_id),
                    "reason": sanitize(reason),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized to access this resource: {reason}",
            )

        return unit

    async def upsert_unit(
        self, unit_data: Unit, user: User, provider: Optional[str] = None
    ) -> Unit:
        """
        Create or update a unit (internal operation).

        This is called during:
        - OAuth sync
        - Provider sync
        - System operations

        NO policy checks - this is internal.
        """
        # Upsert unit
        unit = await self.unit_repo.upsert(
            unit_data, user_id=user.id, provider=user.provider
        )

        logger.info(
            "Unit upserted (internal)",
            extra={
                "unit_id": unit.id,
                "user_id": user.id,
            },
        )

        return unit

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count units with optional filters."""
        return await self.unit_repo.count(filters)
