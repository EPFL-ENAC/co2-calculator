"""The recalculate-emissions endpoints admit either backoffice edit grant (#3153)."""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.utils.scoping import require_pipeline_ops_or_config_edit


def _user_with_perms(perms: dict[str, list[str]]) -> MagicMock:
    user = MagicMock()
    user.calculate_permissions.return_value = perms
    return user


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path", ["backoffice.pipeline_operations", "backoffice.configuration"]
)
async def test_either_edit_grant_passes(path):
    user = _user_with_perms({path: ["view", "edit"]})
    dep = require_pipeline_ops_or_config_edit()
    assert await dep(current_user=user) is user


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "perms",
    [
        {},
        {
            "backoffice.pipeline_operations": ["view"],
            "backoffice.configuration": ["view"],
        },
        # A sub-perimeter grant must not unlock a recalc over every unit.
        {"backoffice.configuration/1234": ["view", "edit"]},
    ],
    ids=["no-perms", "view-only", "scoped-edit"],
)
async def test_without_bare_edit_grant_fails_closed(perms):
    user = _user_with_perms(perms)
    dep = require_pipeline_ops_or_config_edit()
    with pytest.raises(HTTPException) as exc:
        await dep(current_user=user)
    assert exc.value.status_code == 403
