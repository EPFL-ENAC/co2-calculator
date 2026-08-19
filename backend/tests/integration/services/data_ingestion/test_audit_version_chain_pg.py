"""The audit hash chain, against the real partial unique index (#2050 J4).

``audit_document_one_current_idx`` is declared with
``postgresql_where=text("is_current = true")``. SQLite ignores that dialect
kwarg and builds a *non-partial* unique index instead, so a second version of
any entity violates it there — which makes SQLite the wrong place to test
versioning at all. This runs on Postgres, where the index means what the
model says.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.audit import AuditChangeTypeEnum
from app.services.audit_service import AuditDocumentService

pytestmark = pytest.mark.asyncio


async def test_create_version_chain_survives_skipping_the_head_lookup(pg_dsn):
    """#2050 J4: a CREATE no longer queries for a previous version — a fresh
    entity id cannot have one. The chain must still come out correct: version
    1 with no previous_hash, and a following UPDATE chained onto it with the
    old head demoted.
    """
    url = pg_dsn.replace("postgresql+asyncpg", "postgresql+psycopg")
    engine = create_async_engine(url, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as session:
            service = AuditDocumentService(session)
            created = await service.create_version(
                entity_type="data_entries",
                entity_id=4242,
                data_snapshot={"fte": 1.0},
                change_type=AuditChangeTypeEnum.CREATE,
                changed_by=1,
                handler_id="TEST-USER",
            )
            assert created.version == 1
            assert created.previous_hash is None
            assert created.is_current is True
            await session.commit()

        async with Sf() as session:
            service = AuditDocumentService(session)
            updated = await service.create_version(
                entity_type="data_entries",
                entity_id=4242,
                data_snapshot={"fte": 2.0},
                change_type=AuditChangeTypeEnum.UPDATE,
                changed_by=1,
                handler_id="TEST-USER",
            )
            await session.commit()

        assert updated.version == 2
        assert updated.previous_hash == created.current_hash
        assert updated.is_current is True
    finally:
        await engine.dispose()
