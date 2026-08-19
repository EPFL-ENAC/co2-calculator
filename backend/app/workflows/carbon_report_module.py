from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.data_entry_permissions import (
    can_delete,
    is_policy_exempt,
    provenance_of,
    writable_fields_for_row,
)
from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.data_entry import DataEntrySourceEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.carbon_report import CarbonReportModuleRead
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponse,
    DataEntryUpdate,
)
from app.schemas.user import UserRead
from app.schemas.write_scope import WriteScope
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.data_entry_emission_service import DataEntryEmissionService
from app.services.data_entry_service import DataEntryService
from app.services.module_handler_service import ModuleHandlerService

logger = get_logger(__name__)


class CarbonReportModuleWorkflow:
    """Base workflow for processing data entries and calculating emissions."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def _check_planner_purchase_exclusivity(
        self,
        carbon_report_module_id: int,
        data_entry_type: DataEntryTypeEnum,
        data: dict,
        exclude_entry_id: int | None = None,
    ) -> None:
        """PRD #1555: submodule CHF totals XOR one global budget.

        Rejects a submodule total while a global budget exists (and vice
        versa), a second global budget, and a duplicate submodule category.
        ``exclude_entry_id`` drops the row being edited from the scan so an
        update that keeps its own category isn't flagged as a self-collision.
        """
        rows = [
            r
            for r in await DataEntryRepository(self.session).list_by_module(
                carbon_report_module_id
            )
            if r.id != exclude_entry_id
        ]
        budgets = [
            r
            for r in rows
            if r.data_entry_type_id == DataEntryTypeEnum.planner_purchase_budget.value
        ]
        totals = [
            r
            for r in rows
            if r.data_entry_type_id == DataEntryTypeEnum.planner_purchase.value
        ]
        if data_entry_type is DataEntryTypeEnum.planner_purchase:
            if budgets:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="PURCHASES_GLOBAL_BUDGET_SET",
                )
            category = data.get("purchase_category")
            if any(r.data.get("purchase_category") == category for r in totals):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="DUPLICATE_PURCHASE_CATEGORY",
                )
            return
        if totals:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="PURCHASES_SUBMODULE_TOTALS_SET",
            )
        if budgets:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="PURCHASES_GLOBAL_BUDGET_EXISTS",
            )

    async def create(
        self,
        carbon_report_module: CarbonReportModuleRead,
        data_entry_type_id: int,
        item_data: dict,
        current_user: UserRead,
        request_context: dict,
        background_tasks: BackgroundTasks,
        scope: WriteScope | None = None,
    ) -> DataEntryResponse:
        try:
            create_payload = {
                **item_data,
                "data_entry_type_id": data_entry_type_id,
                "carbon_report_module_id": carbon_report_module.id,
            }
            data_entry_type = DataEntryTypeEnum(data_entry_type_id)
            handler = BaseModuleHandler.get_by_type(data_entry_type)

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

        if data_entry_type in (
            DataEntryTypeEnum.planner_purchase,
            DataEntryTypeEnum.planner_purchase_budget,
        ):
            await self._check_planner_purchase_exclusivity(
                carbon_report_module.id,
                data_entry_type,
                validated_data.model_dump(),
            )

        try:
            item = await DataEntryService(self.session).create(
                carbon_report_module_id=carbon_report_module.id,
                data_entry_type_id=data_entry_type_id,
                user=UserRead.model_validate(current_user),
                data=data_entry_create,
                request_context=request_context,
                background_tasks=background_tasks,
                source=DataEntrySourceEnum.USER_MANUAL.value,
                created_by_id=current_user.id,
                scope=scope,
            )
            if item is None:
                raise HTTPException(
                    status_code=500,
                    detail="Failed to create item",
                )

            # #2050 J4: ``create``, not ``upsert_by_data_entry`` — the entry
            # was inserted a few statements ago and cannot have emissions to
            # replace, so upsert's pre-delete lookup is a guaranteed-empty
            # SELECT. The update path below keeps using upsert.
            await DataEntryEmissionService(self.session).create(item, scope=scope)
            # #2050 J9: the report rollup stays in this transaction. J4
            # deferred it on the premise that nobody reads report totals in
            # this interaction; the frontend's own waterfall disproves that —
            # it fetches report-stats right after the write, and that endpoint
            # serves the persisted carbon_reports.stats column.
            await CarbonReportModuleService(self.session).recompute_stats(
                carbon_report_module.id, scope=scope
            )
            await self.session.commit()
        except IntegrityError as e:
            await self.session.rollback()
            # #2050 J4: the member-role uniqueness pre-check is gone. The
            # unique index reports the same condition, without the
            # check-then-act race two concurrent POSTs used to both win.
            if "uq_member_role_per_module" in str(e.orig):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="DUPLICATE_INSTITUTIONAL_ID",
                ) from e

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
            # Overlay the incoming partial PATCH on the persisted data so factor
            # resolution and validation see the full record. A classification
            # PATCH (e.g. sub_class only) otherwise drops the persisted kind
            # (equipment_class) — resolving the factor with an empty kind and
            # validating an incomplete entity (issue: lost equipment_class).
            update_payload = {
                **existing_data,
                **item_data,
                "data_entry_type_id": data_entry_type_id,
                "carbon_report_module_id": carbon_report_module.id,
            }
            data_entry_type = DataEntryTypeEnum(data_entry_type_id)
            handler = BaseModuleHandler.get_by_type(data_entry_type)
            # No factor resolution on update: subkind/override code that
            # belonged to the old kind are cleared, everything else is the
            # emission compute's job (it resolves on its own).
            update_payload = ModuleHandlerService.clear_dependent_fields_on_kind_change(
                handler,
                update_payload,
                item_data,
                existing_data,
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
        # Outside the validation try so its 422 code isn't swallowed into a
        # generic 400 (matches the create() placement).
        if data_entry_type in (
            DataEntryTypeEnum.planner_purchase,
            DataEntryTypeEnum.planner_purchase_budget,
        ):
            await self._check_planner_purchase_exclusivity(
                carbon_report_module.id,
                data_entry_type,
                validated_data.model_dump(),
                exclude_entry_id=item_id,
            )
        if current_user.id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current user ID is required to update item",
            )
        if not is_policy_exempt(data_entry_type):
            module_type = ModuleTypeEnum(carbon_report_module.module_type_id)
            # DataEntryService.get() (line 226) always raises on a missing
            # entry, never returns None — existing_entry is guaranteed here.
            allowed = writable_fields_for_row(
                module_type, data_entry_type, existing_entry.source
            )
            # Diffs the caller's literal item_data, not update_payload — the
            # latter can carry dependent-field resets from
            # clear_dependent_fields_on_kind_change() (e.g. Purchase's
            # purchase_additional_code nulled when purchase_institutional_code
            # changes). Those are data-integrity cascades of an ALLOWED edit,
            # not a user attempting to write a locked field directly, and are
            # intentionally not checked here (decision 2026-08-13, code
            # review; see test_update_purchase_kind_change_clears_locked_
            # dependent_field for the pinned behavior).
            changed_locked_fields = [
                field
                for field, value in item_data.items()
                if field not in allowed and existing_data.get(field) != value
            ]
            if changed_locked_fields:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "code": "FIELD_NOT_EDITABLE",
                        "fields": changed_locked_fields,
                    },
                )
        # #951: SCIPER (user_institutional_id) is now updatable on a user
        # row (policy-gated above); mirrors create()'s uniqueness check
        # (a person can hold multiple roles, so the key is the pair, not
        # just the person) — same check the DTO can't express, now needed
        # on update too since the field wasn't writable before.
        if data_entry_type == DataEntryTypeEnum.member and (
            "user_institutional_id" in item_data or "sius_code" in item_data
        ):
            member_data = validated_data.model_dump()
            uid = member_data.get("user_institutional_id")
            sius_code = member_data.get("sius_code")
            if uid and sius_code:
                is_unique = await DataEntryService(
                    self.session
                ).check_member_role_unique(
                    carbon_report_module_id=carbon_report_module.id,
                    uid=uid,
                    sius_code=sius_code,
                    exclude_id=item_id,
                )
                if not is_unique:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail="DUPLICATE_INSTITUTIONAL_ID",
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
        try:
            entry = await DataEntryService(self.session).get(id=data_entry_id)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
            ) from e
        data_entry_type = DataEntryTypeEnum(entry.data_entry_type_id)
        if not is_policy_exempt(data_entry_type) and not can_delete(
            provenance_of(entry.source)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "ROW_NOT_DELETABLE"},
            )
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
