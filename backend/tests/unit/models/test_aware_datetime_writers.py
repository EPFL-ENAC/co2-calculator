"""#2956 — writers of the timestamptz columns produce timezone-aware values.

``DateTime(timezone=True)`` silently accepts a naive value, which PostgreSQL
then reads in the session TimeZone, so these tests are the guard, not the
column type. They check the in-memory value: a DB round trip proves nothing,
since SQLite drops tzinfo and timestamptz always comes back aware.

The ``last_login`` and ``synced_at`` writers are pinned in
``test_user_repo.py`` and ``test_audit_sync_service.py``.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.sql.schema import CallableColumnDefault
from sqlmodel import SQLModel

from app.api.v1.year_configuration import create_audit_entry
from app.models.audit import AuditChangeTypeEnum, AuditDocument
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration


def test_audit_document_changed_at_default_is_aware():
    doc = AuditDocument(
        entity_type="year_configuration",
        entity_id=20250,
        version=1,
        data_snapshot={},
        change_type=AuditChangeTypeEnum.CREATE,
        handler_id="handler",
        ip_address="127.0.0.1",
        current_hash="hash",
    )

    assert doc.changed_at.tzinfo is not None


def test_year_configuration_updated_at_default_and_onupdate_are_aware():
    config = YearConfiguration(year=2025, provider=UserProvider.DEFAULT)
    onupdate = SQLModel.metadata.tables["year_configuration"].c.updated_at.onupdate

    assert config.updated_at.tzinfo is not None
    assert isinstance(onupdate, CallableColumnDefault)
    assert onupdate.arg(None).tzinfo is not None


@pytest.mark.asyncio
async def test_year_configuration_audit_entry_changed_at_is_aware():
    no_previous_version = MagicMock()
    no_previous_version.first.return_value = None
    session = MagicMock()
    session.exec = AsyncMock(return_value=no_previous_version)
    user = MagicMock(id=1, provider=UserProvider.DEFAULT, institutional_id="123")

    await create_audit_entry(
        session, 2025, AuditChangeTypeEnum.UPDATE, user, data_snapshot={}
    )

    entry = session.add.call_args.args[0]
    assert isinstance(entry, AuditDocument)
    assert entry.changed_at.tzinfo is not None
