from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.schemas.carbon_report import CarbonReportModuleRead
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponse,
    DataEntryUpdate,
)
from app.schemas.user import UserRead
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.module_handler_service import ModuleHandlerService

logger = get_logger(__name__)


class CarbonReportModuleWorkflow:
    """
    Base workflow for processing data entries and calculating emissions.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry_type_id: int,
        item_data: dict,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> DataEntryResponse:
        try:
            create_payload = {
                **item_data,
                "data_entry_type_id": data_entry_type_id,
                "carbon_report_module_id": carbon_report_module.id,
            }
            data_entry_type = DataEntryTypeEnum(data_entry_type_id)
            handler = BaseModuleHandler.get_by_type(data_entry_type)
            handler_service = ModuleHandlerService(self.session)
            create_payload = await handler_service.resolve_primary_factor_id(
                handler, create_payload, data_entry_type
            )

            validated_data = handler.validate_create(create_payload)

            data_entry_create = DataEntryCreate(
                **validated_data.model_dump(exclude_unset=True)
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(
                "Error validating item_data for data entry creation",
                extra={"error": str(e), "item_data": sanitize(item_data)},
            )
            raise HTTPException(
                status_code=400,
                detail=f"Invalid item_data for creation: {str(e)}",
            )

        if data_entry_type == DataEntryTypeEnum.member and validated_data.model_dump().get(
            "user_institutional_id"
        ):
            uid = validated_data.model_dump()["user_institutional_id"]
            is_unique = await DataEntryService(self.session).check_institutional_id_unique(
                carbon_report_module_id=carbon_report_module.id,
                uid=uid,
            )
            if not is_unique:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="DUPLICATE_INSTITUTIONAL_ID",
                )

        try:
            item = await DataEntryService(self.session).create(
                carbon_report_module_id=carbon_report_module.id,
                data_entry_type_id=data_entry_type_id,
                user=UserRead.model_validate(current_user),
                data=data_entry_create,
                request_context=request_context,
                background_tasks=background_tasks,
            )
            if item is None:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create item",
                )

            await DataEntryEmissionService(self.session).upsert_by_data_entry(
                data_entry_response=item,
            )
            await CarbonReportModuleService(self.session).recompute_stats(
                carbon_report_module.id
            )
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()

            if "data_entries_unique_member_uid_per_module_idx" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="This user institutional id already exists in this module.",
                )

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Database integrity error.",
            ) from e

        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Failed to create data entry for "
                f"module_id={carbon_report_module.module_type_id}",
                exc_info=True,
            )

            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create data entry",
            ) from e

        response = DataEntryResponse.model_validate(item)
        # todo kg_co2eq in response is never used and can be removed,
        # but for now set to 0 to avoid confusion until we clean up
        # the schema
        response.data = {
            **response.data,
            "kg_co2eq": 0,
        }
        logger.info(f"Created {carbon_report_module.module_type_id}:{response.id}")

        return response

    async def update(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry_type_id: int,
        item_id: int,
        item_data: dict,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> DataEntryResponse:
        try:
            existing_entry = await DataEntryService(self.session).get(id=item_id)
            existing_data = existing_entry.data if existing_entry else {}
            update_payload = {
                **item_data,
                "data_entry_type_id": data_entry_type_id,
                "carbon_report_module_id": carbon_report_module.id,
            }
            data_entry_type = DataEntryTypeEnum(data_entry_type_id)
            handler = BaseModuleHandler.get_by_type(data_entry_type)
            handler_service = ModuleHandlerService(self.session)
            update_payload = await handler_service.resolve_primary_factor_if_changed(
                handler, update_payload, data_entry_type, item_data, existing_data
            )

            # For equipment partial PATCH, validate against merged persisted+incoming
            # values so active+standby weekly sum constraints are always enforced.
            # TODO: we should validate on merge data also for patch

            validated_data = handler.validate_update(update_payload)

            data_entry_update = DataEntryUpdate(
                **validated_data.model_dump(exclude_unset=True)
            )
        except Exception as e:
            logger.error(
                f"Error validating update data for item_id={item_id}: {str(e)}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid item_data for update: {str(e)}",
            )
        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current user ID is required to update item",
            )
        try:
            item = await DataEntryService(self.session).update(
                id=item_id,
                data=data_entry_update,
                user=current_user,
                request_context=request_context,
                background_tasks=background_tasks,
            )
            await self.session.flush()
            if item is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Data entry item not found",
                )
            # Recalculate emission after update
            await DataEntryEmissionService(self.session).upsert_by_data_entry(
                data_entry_response=item,
            )
            await CarbonReportModuleService(self.session).recompute_stats(
                carbon_report_module.id
            )
            # upsert could fail if emission factor lookup fails, but we still want to
            # return the updated item
            await self.session.commit()
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Failed to update item_id={item_id}",
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update data entry",
            ) from e
        logger.info(f"Updated item {item_id}")
        return item

    async def delete(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry_id: int,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
    ) -> None:
        await DataEntryService(self.session).delete(
            id=data_entry_id,
            current_user=current_user,
            request_context=request_context,
            background_tasks=background_tasks,
        )
        await CarbonReportModuleService(self.session).recompute_stats(
            carbon_report_module.id
        )
        await self.session.commit()
