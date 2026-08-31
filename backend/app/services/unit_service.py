"""Unit service for business logic with Policy integration."""

from typing import Any

from fastapi import HTTPException, status
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.core.policy import query_policy, require_unit_access
from app.core.role_priority import role_priority_case
from app.models.unit import Unit
from app.models.unit_user import UnitUser
from app.models.user import User
from app.repositories.unit_repo import UnitRepository, UpsertResult
from app.schemas.unit import UnitRead

logger = get_logger(__name__)


class UnitService:
    """Service for unit business logic and orchestration."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.unit_repo = UnitRepository(session)

    def _build_policy_input(self, user: User, action: str) -> dict:
        """Build OPA input data from user context.

        The per-unit resource branch left with get_by_id's policy call
        (#2379) — get_user_units is the only remaining consumer.
        """
        return {
            "action": action,
            "resource_type": "unit",
            "user": {"id": user.id, "email": user.email, "roles": user.roles or []},
            "filters": {},
        }

    async def get_user_units(self, user: User) -> list[dict]:
        """List units with policy authorization and enriched user data.

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
                "principal_user_institutional_id": "67890",
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
            },
        )

        # 3. Extract filters from policy decision
        filters = decision.get("filters", {})

        # 4. Build complex query with joins (service-level orchestration)
        columns: list[Any] = [
            Unit,
            UnitUser.role,
            col(User.display_name).label("principal_user_name"),
            col(User.function).label("principal_user_function"),
            col(User.email).label("principal_user_email"),
        ]
        query: Any = (
            select(*columns)
            .select_from(Unit)
            .join(UnitUser, col(UnitUser.unit_id) == col(Unit.id))
            .outerjoin(
                User,
                col(User.institutional_id) == col(Unit.principal_user_institutional_id),
            )
            .where(col(UnitUser.user_id) == user.id)
            # Workspace surfaces only level-4 (leaf labs) per #930;
            # ancestor levels (EPFL/faculty/institute) have no own data.
            .where(col(Unit.level) == 4)
        )

        # Apply filters from policy engine
        if "unit_id" in filters:  # Keep as unit_id for policy compatibility
            unit_ids = filters["unit_id"]
            if isinstance(unit_ids, list):
                query = query.where(col(Unit.id).in_(unit_ids))
            else:
                query = query.where(Unit.id == unit_ids)

        # #2379: no offset/limit. The join bounds the result by the user's
        # own membership rows — a limit here silently truncated the session
        # bootstrap and the stats accessible-unit filter past 100 units.
        role_case = role_priority_case(UnitUser.role)
        query = query.order_by(role_case)

        result = await self.session.exec(query)
        rows = result.all()

        # Convert to dict format
        return [
            {
                "id": unit.id,
                "name": unit.name,
                "institutional_id": unit.institutional_id,
                "current_user_role": role,
                "principal_user_institutional_id": unit.principal_user_institutional_id,
                "principal_user_name": principal_user_name,
                "principal_user_function": principal_user_function,
                "principal_user_email": principal_user_email,
                "affiliations": unit.path_name.split(" ") if unit.path_name else [],
            }
            for (
                unit,
                role,
                principal_user_name,
                principal_user_function,
                principal_user_email,
            ) in rows
        ]

    async def get_by_institutional_id(self, institutional_id: str) -> UnitRead | None:
        """Get a unit by its institutional_id."""
        unit = await self.unit_repo.get_by_institutional_id(institutional_id)
        if unit is None:
            return None
        return UnitRead.model_validate(unit)

    async def get_by_id(self, id: int, user: User) -> Unit:
        """Get a unit by ID, refusing users with no qualifying role.

        #2379: this used to ask query_policy("authz/resource/read"), whose
        legacy fallback allowed everyone — the workspace guard's probe
        (#2369) authorized nothing, and refusals surfaced one call later at
        the workspace boundary (#2570). Reusing require_unit_access — the
        workspace boundary's own enforcer — makes the probe predict that
        call by construction; two rules cannot drift.

        Raises:
            HTTPException 404: unknown id. Kept ahead of the access check —
                require_unit_access lets global-scope roles through before
                its own None check, so a superadmin probing a deleted id
                would otherwise get a phantom success.
            HTTPException 403: no global- or unit-scoped role for this unit.
        """
        unit = await self.unit_repo.get_by_id(id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found"
            )
        require_unit_access(user, unit)
        return unit

    async def upsert(self, unit_data: Unit) -> Unit:
        """Create or update a unit (internal operation).

        This is called during:
        - OAuth sync
        - Provider sync
        - System operations

        NO policy checks - this is internal.

        NOTE: Caller is responsible for committing the transaction.
        (This allows batching multiple upserts in a single transaction)
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

    async def bulk_create(
        self,
        units: list[Unit],
    ) -> UpsertResult:
        """Bulk create units."""
        logger.info(f"Bulk creating/updating {len(units)} units")
        db_objs = await self.unit_repo.bulk_upsert(units)
        await self.session.flush()  # Ensure unit IDs are populated
        return db_objs

    async def bulk_upsert(self, units: list[Unit]) -> UpsertResult:
        """Upsert units — business logic goes here if needed
        (validation, enrichment, etc.)
        """
        db_objs = await self.unit_repo.bulk_upsert(units)
        await self.session.flush()  # Ensure unit IDs are populated
        return db_objs

    async def get_by_institutional_ids(
        self, institutional_ids: list[str]
    ) -> list[Unit]:
        """Get units by their institutional IDs (batch lookup, no policy checks)."""
        return await self.unit_repo.get_by_institutional_ids(institutional_ids)

    async def count(self, filters: dict | None = None) -> int:
        """Count units with optional filters."""
        return await self.unit_repo.count(filters)
