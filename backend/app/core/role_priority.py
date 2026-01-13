from typing import Iterable, List, Optional

import sqlmodel as sa

from app.models.user import Role, RoleName, RoleScope

ROLE_PRIORITY = {
    RoleName.CO2_USER_PRINCIPAL: 0,
    RoleName.CO2_USER_SECONDARY: 1,
    RoleName.CO2_USER_STD: 2,
}


def pick_role_for_provider_code(
    roles: Optional[Iterable[Role]], provider_code: str
) -> Optional[RoleName]:
    if not roles:
        return None
    candidates: List[RoleName] = [
        r.role
        for r in roles
        if isinstance(r.on, RoleScope) and r.on.provider_code == provider_code
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda r: ROLE_PRIORITY.get(r, 99))


def role_priority_case(column):
    whens = [(column == role, prio) for role, prio in ROLE_PRIORITY.items()]
    return sa.case(*whens, else_=99)
