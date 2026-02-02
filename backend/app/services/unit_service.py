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
from app.schemas.unit import UnitRead

logger = get_logger(__name__)


class UnitService:
    """Service for unit business logic and orchestration."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.unit_repo = UnitRepository(session)

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
            "filters": {},
        }

        if unit:
            input_data["resource"] = {
                "id": unit.id,
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
                "current_user_role": "co2.user.principal",
                "principal_user_provider_code": "67890",
                "affiliations": ["ENAC", "ENAC-IT"],
            }
        """
        # 1. Build policy input
        input_data = self._build_policy_input(user, "read")

        # 2. Query policy for authorization decision
        decision = await query_policy("unit:query", input_data)
        logger.info(
            "Policy decision requested",
            extra={
                "user_id": sanitize(user.id),
                "action": "list_user_units",
                "decision": sanitize(decision),
                "input_data": sanitize(input_data),
            },
        )

        # 3. Extract filters from policy decision
        filters = decision.get("filters", {})

        # 4. Build complex query with joins (service-level orchestration)
        query: Select = (
            select(
                Unit,
                UnitUser.role,
                col(User.display_name).label("principal_user_name"),
                col(User.function).label("principal_user_function"),
            )
            .select_from(Unit)
            # Wrap the join conditions in col()
            .join(UnitUser, col(UnitUser.unit_id) == col(Unit.id))
            .outerjoin(
                User, col(User.provider_code) == col(Unit.principal_user_provider_code)
            )
            .where(col(UnitUser.user_id) == user.id)
        )

        # Apply filters from policy engine
        if "unit_id" in filters:  # Keep as unit_id for policy compatibility
            unit_ids = filters["unit_id"]
            if isinstance(unit_ids, list):
                query = query.where(col(Unit.id).in_(unit_ids))
            else:
                query = query.where(Unit.id == unit_ids)

        role_case = role_priority_case(UnitUser.role)
        query = query.order_by(role_case).offset(skip).limit(limit)

        result = await self.session.execute(query)
        rows = result.all()

        # Convert to dict format
        return [
            {
                "id": unit.id,
                "name": unit.name,
                "current_user_role": role,
                "principal_user_provider_code": unit.principal_user_provider_code,
                "principal_user_name": principal_user_name,
                "principal_user_function": principal_user_function,
                "affiliations": unit.affiliations or [],
            }
            for unit, role, principal_user_name, principal_user_function in rows
        ]

    async def get_by_provider_code(self, provider_code: str) -> Optional[UnitRead]:
        """Get a unit by its provider code."""
        unit = await self.unit_repo.get_by_code(provider_code)
        if unit is None:
            return None
        return UnitRead.model_validate(unit)

    async def get_by_id(self, id: int, user: User) -> Unit:
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
        unit = await self.unit_repo.get_by_id(id)
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
                "unit_id": sanitize(id),
            },
        )

        if not decision.get("allow", False):
            reason = decision.get("reason", "Access denied")
            logger.warning(
                "OPA denied resource read",
                extra={
                    "user_id": sanitize(user.id),
                    "unit_id": sanitize(id),
                    "reason": sanitize(reason),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not authorized to access this resource: {reason}",
            )

        return unit

    async def upsert(self, unit_data: Unit) -> Unit:
        """
        Create or update a unit (internal operation).

        This is called during:
        - OAuth sync
        - Provider sync
        - System operations

        NO policy checks - this is internal.
        """
        # Upsert unit
        unit = await self.unit_repo.upsert(unit_data)

        logger.info(
            "Unit upserted (internal)",
            extra={
                "unit_id": unit.id,
            },
        )

        return unit

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count units with optional filters."""
        return await self.unit_repo.count(filters)
