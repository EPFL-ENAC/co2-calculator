"""Regression: ``create_version`` normalizes snapshots at the boundary.

The audit snapshot lands in a JSON column serialized by the plain
``json.dumps`` configured in ``app.db`` (no ``default=``), so a datetime
(or UUID/Decimal) in any caller's snapshot 500'd the flush — first hit by
the job ``created_at`` on ``POST /v1/sync/dispatch`` (2026-07-17). The
encoder now runs once inside ``create_version`` so the invariant no
longer lives in N call sites.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.audit import AuditChangeTypeEnum
from app.services.audit_service import AuditDocumentService


@pytest.mark.asyncio
async def test_create_version_accepts_datetime_carrying_snapshot(
    db_session: AsyncSession,
):
    doc = await AuditDocumentService(db_session).create_version(
        entity_type="DataIngestionJob",
        entity_id=1,
        data_snapshot={
            "created_at": datetime.now(timezone.utc),
            "pipeline_id": uuid4(),
            "state": 2,
        },
        change_type=AuditChangeTypeEnum.CREATE,
        changed_by=1,
        handler_id="test",
    )
    # The flush inside create_version serializes the JSON column — reaching
    # here without TypeError is the regression guard; the stored snapshot
    # must be JSON-native.
    assert isinstance(doc.data_snapshot["created_at"], str)
    assert isinstance(doc.data_snapshot["pipeline_id"], str)
