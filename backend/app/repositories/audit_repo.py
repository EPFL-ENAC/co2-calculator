from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import String, cast, func, or_
from sqlmodel import col, desc, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.audit import AuditChangeTypeEnum, AuditDocument


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

    async def bulk_create(
        self,
        documents: List[AuditDocument],
    ) -> List[AuditDocument]:
        """Bulk create multiple audit documents."""
        for doc in documents:
            self.session.add(doc)
        await self.session.flush()
        # Refresh all documents to populate IDs
        for doc in documents:
            await self.session.refresh(doc)
        return documents

    def _apply_filters(self, stmt, filters: Dict[str, Any]):
        """Apply common filters to a query statement.

        Args:
            stmt: SQLModel select statement
            filters: Dictionary with optional keys:
                - user_id: filter by changed_by
                - handler_id: filter by handler_id (provider code)
                - entity_type: filter by entity_type
                - entity_id: filter by entity_id
                - action: AuditChangeTypeEnum value
                - date_from: datetime lower bound (inclusive)
                - date_to: datetime upper bound (inclusive)
                - search: free-text search on changed_by, change_reason, entity_type
                - module: filter by route_path prefix or entity_type grouping
        """
        if filters.get("user_id") is not None:
            user_id = filters["user_id"]
            stmt = stmt.where(col(AuditDocument.changed_by) == user_id)

        if filters.get("handler_id") is not None:
            handler_id = str(filters["handler_id"])
            stmt = stmt.where(col(AuditDocument.handler_id) == handler_id)

        if filters.get("entity_type"):
            stmt = stmt.where(col(AuditDocument.entity_type) == filters["entity_type"])

        if filters.get("entity_id") is not None:
            stmt = stmt.where(col(AuditDocument.entity_id) == filters["entity_id"])

        if filters.get("action"):
            action = filters["action"]
            if isinstance(action, str):
                action = AuditChangeTypeEnum(action)
            stmt = stmt.where(col(AuditDocument.change_type) == action)

        if filters.get("date_from"):
            stmt = stmt.where(col(AuditDocument.changed_at) >= filters["date_from"])

        if filters.get("date_to"):
            stmt = stmt.where(col(AuditDocument.changed_at) <= filters["date_to"])

        if filters.get("search"):
            search_term = f"%{filters['search']}%"
            stmt = stmt.where(
                or_(
                    cast(col(AuditDocument.changed_by), String).ilike(search_term),
                    col(AuditDocument.change_reason).ilike(search_term),
                    col(AuditDocument.entity_type).ilike(search_term),
                    col(AuditDocument.route_path).ilike(search_term),
                )
            )

        if filters.get("module"):
            module = filters["module"]
            stmt = stmt.where(
                or_(
                    col(AuditDocument.route_path).ilike(f"%{module}%"),
                    col(AuditDocument.entity_type).ilike(f"%{module}%"),
                )
            )

        return stmt

    async def query(
        self,
        filters: Dict[str, Any],
        page: int = 1,
        page_size: int = 25,
        sort_by: str = "changed_at",
        sort_desc: bool = True,
    ) -> Tuple[List[AuditDocument], int]:
        """Paginated, filtered, sorted query.

        Returns:
            Tuple of (results, total_count)
        """
        # Count query
        count_stmt = select(func.count()).select_from(AuditDocument)
        count_stmt = self._apply_filters(count_stmt, filters)
        count_result = await self.session.exec(count_stmt)
        total = count_result.one()

        # Data query
        stmt = select(AuditDocument)
        stmt = self._apply_filters(stmt, filters)

        # Sorting
        sort_column = getattr(AuditDocument, sort_by, AuditDocument.changed_at)
        if sort_desc:
            stmt = stmt.order_by(desc(sort_column))
        else:
            stmt = stmt.order_by(sort_column)

        # Pagination
        offset = (page - 1) * page_size
        stmt = stmt.offset(offset).limit(page_size)

        result = await self.session.exec(stmt)
        return list(result.all()), total

    async def count_by_change_type(
        self,
        filters: Dict[str, Any],
    ) -> Dict[str, int]:
        """Count audit entries grouped by change_type, with same filters.

        Returns:
            Dictionary with change_type as key and count as value,
            e.g. {"CREATE": 100, "UPDATE": 50, "DELETE": 10, "READ": 200}
        """
        stmt = select(
            AuditDocument.change_type,
            func.count().label("count"),
        ).group_by(AuditDocument.change_type)
        stmt = self._apply_filters(stmt, filters)

        result = await self.session.exec(stmt)
        rows = result.all()

        counts: Dict[str, int] = {}
        for row in rows:
            # row is a tuple (change_type, count)
            change_type_value = (
                row[0].value if hasattr(row[0], "value") else str(row[0])
            )
            counts[change_type_value] = row[1]
        return counts

    async def get_by_id(self, doc_id: int) -> Optional[AuditDocument]:
        """Get a single audit document by its primary key."""
        stmt = select(AuditDocument).where(col(AuditDocument.id) == doc_id)
        result = await self.session.exec(stmt)
        return result.one_or_none()
