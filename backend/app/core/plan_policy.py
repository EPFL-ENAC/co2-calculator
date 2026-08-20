"""Per-request authorization policy for Simulator Plan projects."""

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.unit import Unit
from app.models.user import User
from app.utils.permissions import resolve_module_scope

PLANNER_PLANS_PERMISSION = "planner.plans"


@dataclass(frozen=True)
class PlanPolicy:
    """The caller's rights on one unit's plans, resolved once per request.

    Breadth comes from the ``planner.plans`` permission key
    (``resolve_module_scope``): ``global`` sees and deletes every plan; ``unit``
    and ``own`` see the plans they created plus the ones shared with the unit
    (``is_viewable_by_unit_members``), and delete only their own. ``plan`` is
    duck-typed on ``created_by`` / ``is_viewable_by_unit_members`` so ORM rows
    and ``SimulatorPlanRead`` DTOs both work.
    """

    user_id: int
    permissions: dict
    institutional_id: str

    @classmethod
    def from_unit(cls, current_user: User, unit: Unit | None) -> PlanPolicy:
        if unit is None or unit.institutional_id is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Unit not found"
            )
        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this unit is not permitted.",
            )
        policy = cls(
            user_id=current_user.id,
            permissions=current_user.calculate_permissions(),
            institutional_id=unit.institutional_id,
        )
        if policy.breadth("view") is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this unit is not permitted.",
            )
        return policy

    @classmethod
    async def for_unit(
        cls, db: AsyncSession, current_user: User, unit_id: int
    ) -> PlanPolicy:
        return cls.from_unit(current_user, await db.get(Unit, unit_id))

    def breadth(self, action: str) -> str | None:
        return resolve_module_scope(
            self.permissions,
            PLANNER_PLANS_PERMISSION,
            action,
            institutional_id=self.institutional_id,
        )

    def can_view(self, plan: Any) -> bool:
        breadth = self.breadth("view")
        if breadth == "global":
            return True
        if breadth is None:
            return False
        return plan.created_by == self.user_id or bool(plan.is_viewable_by_unit_members)

    def can_edit(self, plan: Any) -> bool:
        return self.can_view(plan)

    def can_delete(self, plan: Any) -> bool:
        breadth = self.breadth("delete")
        if breadth == "global":
            return True
        if breadth is None:
            return False
        return plan.created_by == self.user_id

    def require(self, plan: Any, action: str) -> None:
        if not self.can_view(plan):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found"
            )
        if action in ("view", "edit"):
            return
        if self.can_delete(plan):
            return
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the plan's creator can delete it.",
        )

    def visible(self, plans: list) -> list:
        return [plan for plan in plans if self.can_view(plan)]
