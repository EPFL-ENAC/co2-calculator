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
async def test_view_only_fails_closed():
    user = _user_with_perms(
        {
            "backoffice.pipeline_operations": ["view"],
            "backoffice.configuration": ["view"],
        }
    )
    dep = require_pipeline_ops_or_config_edit()
    with pytest.raises(HTTPException) as exc:
        await dep(current_user=user)
    assert exc.value.status_code == 403
