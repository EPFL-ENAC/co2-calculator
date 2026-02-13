"""DataEntry service for business logic."""

from datetime import datetime, timezone
from typing import Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.audit import AuditChangeTypeEnum
from app.models.data_entry import DataEntry, DataEntryTypeEnum

# from app.repositories.headcount_repo import HeadCountRepository
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report_response import (
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
)
from app.schemas.data_entry import DataEntryCreate, DataEntryResponse, DataEntryUpdate
from app.schemas.user import UserRead
from app.services.audit_service import AuditDocumentService
from app.utils.audit_helpers import extract_handled_ids, extract_handled_ids_from_list

logger = get_logger(__name__)


class DataEntryService:
    """Service for data entry business logic."""

    def __init__(
        self,
        session: AsyncSession,
        versioning_service: Optional[AuditDocumentService] = None,
    ):
        self.session = session
        self.repo = DataEntryRepository(session)
        self.versioning = versioning_service or AuditDocumentService(session)

    async def get_stats(
        self,
        carbon_report_module_id: int,
        aggregate_by: str = "data_entry_type_id",
        aggregate_field: str = "fte",
    ) -> dict[str, float]:
        """Get module statistics such as total items and submodules."""
        return await self.repo.get_stats(
            carbon_report_module_id=carbon_report_module_id,
            aggregate_by=aggregate_by,
            aggregate_field=aggregate_field,
        )

    async def create(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: int,
        user: UserRead,
        data: DataEntryCreate,
        request_context: Optional[dict] = None,
    ) -> DataEntryResponse:
        logger.info(
            f"Creating data entry for module_id={sanitize(carbon_report_module_id)} "
            f"data_entry_type_id={sanitize(data_entry_type_id)} "
            f"user_id={sanitize(user.id)}"
        )
        entry = DataEntry(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=data_entry_type_id,
            data=data.data,
        )

        created_entry = await self.repo.create(entry)

        # 3. replace by flush; commit should happen in 'orchestrator' or 'route'
        # top level domain)
        await self.session.flush()
        await self.session.refresh(created_entry)

        # Extract context information
        request_context = request_context or {}
        handled_ids = extract_handled_ids(
            created_entry, DataEntryTypeEnum(data_entry_type_id)
        )

        await self.versioning.create_version(
            entity_type=self.repo.entity_type,
            entity_id=created_entry.id or 0,
            data_snapshot=created_entry.model_dump(),
            change_type=AuditChangeTypeEnum.CREATE,
            changed_by=str(user.id),
            change_reason="Initial creation",
            handler_id=user.provider_code,
            handled_ids=handled_ids,
            ip_address=request_context.get("ip_address"),
            route_path=request_context.get("route_path"),
            route_payload=request_context.get("route_payload"),
        )

        # 5. return response
        return DataEntryResponse.model_validate(created_entry)

    async def bulk_create(
        self,
        data_entries: list[DataEntry],
        user: Optional[UserRead] = None,
        request_context: Optional[dict] = None,
        job_id: Optional[str | int] = None,
    ) -> list[DataEntryResponse]:
        """Bulk create data entries."""
        logger.info(f"Bulk creating {len(data_entries)} data entries")
        db_objs = await self.repo.bulk_create(data_entries)
        await self.session.flush()  # Ensure data_entry IDs are populated

        # Create version for each created entry (only if user context available)
        if user or job_id:
            request_context = request_context or {}
            changed_by = str(user.id) if user else str(job_id)
            handler_id = user.provider_code if user else "csv_ingestion"

            for obj in db_objs:
                handled_ids = extract_handled_ids(
                    obj, DataEntryTypeEnum(obj.data_entry_type_id)
                )

                await self.versioning.create_version(
                    entity_type=self.repo.entity_type,
                    entity_id=obj.id or 0,
                    data_snapshot=obj.model_dump(),
                    change_type=AuditChangeTypeEnum.CREATE,
                    changed_by=changed_by,
                    change_reason="Bulk data entry creation"
                    if user
                    else f"Imported via CSV job {job_id}",
                    handler_id=handler_id,
                    handled_ids=handled_ids,
                    ip_address=request_context.get("ip_address"),
                    route_path=request_context.get("route_path"),
                    route_payload=request_context.get("route_payload"),
                )

        return [DataEntryResponse.model_validate(obj) for obj in db_objs]

    async def bulk_delete(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: DataEntryTypeEnum,
        user: Optional[UserRead] = None,
        request_context: Optional[dict] = None,
    ) -> None:
        """Bulk delete data entries by module and type."""
        logger.info(
            f"Bulk deleting data entries\n"
            f"for module_id={sanitize(carbon_report_module_id)}\n"
            f"data_entry_type_id={sanitize(data_entry_type_id.value)}"
        )

        # Fetch entries before deletion to capture snapshots (only if versioning needed)
        entries_to_delete = []
        snapshots = {}
        handled_ids_map = {}
        if user:
            entries_to_delete = await self.repo.get_list(
                carbon_report_module_id=carbon_report_module_id,
                limit=10000,
                offset=0,
                sort_by="id",
                sort_order="asc",
            )
            # Filter to only the type being deleted
            entries_to_delete = [
                e
                for e in entries_to_delete
                if e.data_entry_type_id == data_entry_type_id
            ]

            # Capture snapshots and handled_ids before deletion
            for e in entries_to_delete:
                snapshots[e.id] = e.model_dump()
                handled_ids_map[e.id] = extract_handled_ids(
                    e, DataEntryTypeEnum(e.data_entry_type_id)
                )

        await self.repo.bulk_delete(carbon_report_module_id, data_entry_type_id)
        await self.session.flush()

        # Create version for each deleted entry (only if user context available)
        if user and entries_to_delete:
            request_context = request_context or {}
            for entry in entries_to_delete:
                await self.versioning.create_version(
                    entity_type=self.repo.entity_type,
                    entity_id=entry.id or 0,
                    data_snapshot=snapshots[entry.id],
                    change_type=AuditChangeTypeEnum.DELETE,
                    changed_by=str(user.id),
                    change_reason="Bulk data entry deletion",
                    handler_id=user.provider_code,
                    handled_ids=handled_ids_map.get(entry.id, []),
                    ip_address=request_context.get("ip_address"),
                    route_path=request_context.get("route_path"),
                    route_payload=request_context.get("route_payload"),
                )

    async def update(
        self,
        id: int,
        data: DataEntryUpdate,
        user: UserRead,
        request_context: Optional[dict] = None,
    ) -> DataEntryResponse:
        """Update an existing record."""
        if not user or not user.id:
            logger.error("User context is required for updating data entry")
            raise PermissionError("User context is required for updating data entry")
        entry = await self.repo.update(
            id=id,
            data=data,
            user_id=user.id,
        )
        if entry is None:
            raise ValueError(f"Data entry with id={id} not found")
        await self.session.refresh(entry)

        # Extract context information
        request_context = request_context or {}
        handled_ids = extract_handled_ids(
            entry, DataEntryTypeEnum(entry.data_entry_type_id)
        )

        await self.versioning.create_version(
            entity_type=self.repo.entity_type,
            entity_id=entry.id or 0,
            data_snapshot=entry.model_dump(),
            change_type=AuditChangeTypeEnum.UPDATE,
            changed_by=str(user.id),
            change_reason="Data entry updated",
            handler_id=user.provider_code,
            handled_ids=handled_ids,
            ip_address=request_context.get("ip_address"),
            route_path=request_context.get("route_path"),
            route_payload=request_context.get("route_payload"),
        )

        return DataEntryResponse.model_validate(entry)

    async def delete(
        self, id: int, current_user: UserRead, request_context: Optional[dict] = None
    ) -> bool:
        """Delete a record."""
        # Fetch entry before deletion to capture snapshot
        entry = await self.repo.get(id)
        if entry is None:
            raise ValueError(f"Data entry with id={id} not found")

        # Capture snapshot and handled_ids before deletion
        snapshot = entry.model_dump()
        handled_ids = extract_handled_ids(
            entry, DataEntryTypeEnum(entry.data_entry_type_id)
        )

        result = await self.repo.delete(id)
        await self.session.flush()

        if result is False:
            raise ValueError(f"Data entry with id={id} not found")

        # Extract context information
        request_context = request_context or {}

        # Create version record for deletion
        await self.versioning.create_version(
            entity_type=self.repo.entity_type,
            entity_id=id,
            data_snapshot=snapshot,
            change_type=AuditChangeTypeEnum.DELETE,
            changed_by=str(current_user.id),
            change_reason="Data entry deleted",
            handler_id=current_user.provider_code,
            handled_ids=handled_ids,
            ip_address=request_context.get("ip_address"),
            route_path=request_context.get("route_path"),
            route_payload=request_context.get("route_payload"),
        )

        return True

    async def get(self, id: int) -> DataEntryResponse:
        """Get record by ID."""
        entry = await self.repo.get(id)
        if entry is None:
            raise ValueError(f"Data entry with id={id} not found")
        return DataEntryResponse.model_validate(entry)

    async def get_list(
        self,
        carbon_report_module_id: int,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "id",
        sort_order: str = "asc",
        filter: Optional[str] = None,
    ) -> list[DataEntryResponse]:
        """Get  record by carbon_report_module_id."""
        entries = await self.repo.get_list(
            carbon_report_module_id, limit, offset, sort_by, sort_order, filter
        )
        return [DataEntryResponse.model_validate(entry) for entry in entries]

    async def get_module_data(
        self,
        carbon_report_module_id: int,
    ) -> ModuleResponse:
        data_entry_types_total_items = await self.repo.get_total_count_by_submodule(
            carbon_report_module_id=carbon_report_module_id
        )
        # more info in routes carbon_report_module (cf DataEntryEmissionService)
        # we just return empty stats and totals, it's computed in routes
        totals = ModuleTotals(
            total_annual_fte=None,
            total_kg_co2eq=None,
            total_tonnes_co2eq=None,
            total_annual_consumption_kwh=None,
        )

        # Create module response
        module_response = ModuleResponse(
            carbon_report_module_id=carbon_report_module_id,
            retrieved_at=datetime.now(timezone.utc),
            data_entry_types_total_items=data_entry_types_total_items,
            stats=None,
            totals=totals,
        )
        return module_response

    async def get_submodule_data(
        self,
        carbon_report_module_id: int,
        data_entry_type_id: int,
        limit: int = 100,
        offset: int = 0,
        sort_by: str = "date",
        sort_order: str = "asc",
        filter: Optional[str] = None,
        current_user: Optional[UserRead] = None,
        request_context: Optional[dict] = None,
    ) -> SubmoduleResponse:
        """Get module data for a unit and year."""
        response = await self.repo.get_submodule_data(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=data_entry_type_id,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )

        if (
            (current_user is not None and current_user.id is not None)
            and (request_context is not None)
            and (
                response is not None
                and data_entry_type_id == DataEntryTypeEnum.trips.value
            )
            or (data_entry_type_id == DataEntryTypeEnum.member.value)
        ):
            # for headcount and trips we need for OPDO to have a record of READ
            # Create version record for read
            extract_handled_ids = extract_handled_ids_from_list(
                response.items, DataEntryTypeEnum(data_entry_type_id)
            )
            await self.versioning.create_version(
                entity_type=self.repo.entity_type,
                entity_id=-1,
                data_snapshot=None,  # No snapshot for read operations
                change_type=AuditChangeTypeEnum.READ,
                changed_by=str(current_user.id),
                change_reason=(
                    f"Data entry read for "
                    f"carbon_report_module_id {carbon_report_module_id} "
                    f"and data_entry_type_id {data_entry_type_id}"
                ),
                handler_id=current_user.provider_code,
                handled_ids=extract_handled_ids,
                ip_address=request_context.get("ip_address"),
                route_path=request_context.get("route_path"),
                route_payload=request_context.get("route_payload"),
            )
            # special case, we want to commit here, cause we don't commit in READ routes
            await self.session.commit()

        return response

    async def get_total_per_field(
        self,
        field_name: str,
        carbon_report_module_id: int,
        data_entry_type_id: Optional[int],
    ) -> Optional[float]:
        """Get total sum of a specific field for a given module and data entry type."""
        return await self.repo.get_total_per_field(
            field_name=field_name,
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=data_entry_type_id,
        )
