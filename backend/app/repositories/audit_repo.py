from typing import List, Optional

from sqlmodel import col, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.audit import AuditDocument


class AuditDocumentRepository:
    """Repository for DataIngestionJob database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        document: AuditDocument,
    ) -> AuditDocument:
        doc = AuditDocument.model_validate(document)
        self.session.add(doc)
        await self.session.flush()
        await self.session.refresh(doc)
        return doc

    async def get(
        self,
        entity_type: str,
        entity_id: int,
        version: Optional[int] = None,
    ) -> Optional[AuditDocument]:
        stmt = select(AuditDocument).where(
            AuditDocument.entity_type == entity_type,
            AuditDocument.entity_id == entity_id,
        )
        if version is not None:
            stmt = stmt.where(AuditDocument.version == version)
        else:
            stmt = stmt.order_by(desc(col(AuditDocument.version)))
        result = await self.session.exec(stmt)
        return result.one_or_none()

    async def list(
        self,
        entity_type: str,
        entity_id: int,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
    ) -> List[AuditDocument]:
        stmt = (
            select(AuditDocument)
            .where(
                AuditDocument.entity_type == entity_type,
                AuditDocument.entity_id == entity_id,
            )
            .order_by(col(AuditDocument.version))
        )

        stmt = stmt.offset(offset) if offset is not None else stmt
        stmt = stmt.limit(limit) if limit is not None else stmt
        result = await self.session.exec(stmt)
        return list(result.all())
