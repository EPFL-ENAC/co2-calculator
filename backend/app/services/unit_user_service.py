"""UnitUser service for business logic and orchestration."""

from typing import List, Optional

from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.unit_user import UnitUser
from app.models.user import RoleName
from app.repositories.unit_repo import UnitRepository
from app.repositories.unit_user_repo import UnitUserRepository
from app.repositories.user_repo import UserRepository

logger = get_logger(__name__)

# Valid roles for unit users
VALID_ROLES = [
    RoleName.CO2_USER_PRINCIPAL,
    RoleName.CO2_USER_STD,
]


class UnitUserService:
    """Service for UnitUser business logic and orchestration."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.unit_user_repo = UnitUserRepository(session)
        self.unit_repo = UnitRepository(session)
        self.user_repo = UserRepository(session)

    def _validate_role(self, role: RoleName) -> None:
        """Validate that role is one of the allowed values."""
        if role not in VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid role. Must be one of: {', '.join(VALID_ROLES)}",
            )

    async def upsert(
        self,
        unit_id: str,
        user_id: str,
        role: RoleName,
    ) -> UnitUser:
        """
        Create or update a UnitUser association with validation.

        Validates:
        - Unit exists
        - User exists
        - Role is valid

        Args:
            unit_id: Unit ID
            user_id: User ID
            role: Role to assign

        Returns:
            Created or updated UnitUser

        Raises:
            HTTPException: If validation fails
        """
        if not role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Role must be provided",
            )
        # Validate role
        self._validate_role(role)

        # Validate unit exists
        unit = await self.unit_repo.get_by_id(unit_id)
        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unit {unit_id} not found",
            )

        # Validate user exists
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User {user_id} not found",
            )

        # Create/update association
        unit_user = await self.unit_user_repo.upsert(unit_id, user_id, role)

        logger.info(
            "UnitUser association upserted",
            extra={
                "unit_id": unit_id,
                "user_id": user_id,
                "role": role,
            },
        )

        return unit_user

    async def get_by_unit_and_user(
        self, unit_id: str, user_id: str
    ) -> Optional[UnitUser]:
        """Get UnitUser association."""
        return await self.unit_user_repo.get_by_unit_and_user(unit_id, user_id)

    async def get_by_user(self, user_id: str) -> List[UnitUser]:
        """Get all units for a user."""
        return await self.unit_user_repo.get_by_user(user_id)

    async def get_by_unit(self, unit_id: str) -> List[UnitUser]:
        """Get all users for a unit."""
        return await self.unit_user_repo.get_by_unit(unit_id)

    async def delete(self, unit_id: str, user_id: str) -> bool:
        """Delete a UnitUser association."""
        result = await self.unit_user_repo.delete(unit_id, user_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="UnitUser association not found",
            )

        logger.info(
            "UnitUser association deleted",
            extra={
                "unit_id": unit_id,
                "user_id": user_id,
            },
        )

        return True

    async def count(self, filters: Optional[dict] = None) -> int:
        """Count UnitUser associations."""
        return await self.unit_user_repo.count(filters)
