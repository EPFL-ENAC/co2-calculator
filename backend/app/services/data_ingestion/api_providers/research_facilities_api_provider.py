"""Research facilities (common) Tableau API provider.

Pulls facility usage rows (facility id/name, use, use unit, unit) from the
research facilities Tableau datasource and persists them as
``research_facilities`` data entries.
"""

from typing import Any

from app.core.logging import get_logger
from app.models.connector import ConnectorType
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.schemas.user import UserRead
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.api_providers.base_tableau_api_provider import (
    BaseTableauApiProvider,
    CaptionSpec,
    StatsDict,
)

logger = get_logger(__name__)


class ResearchFacilitiesApiProvider(BaseTableauApiProvider):
    """Research facilities (common) provider backed by the EPFL Tableau
    connection.

    Credentials + datasource LUID come from the DB via the base class; this
    subclass owns only the facility-specific transform/load.
    """

    CONNECTOR = ConnectorType.EPFL_TABLEAU
    MODULE_TYPE = ModuleTypeEnum.research_facilities
    DATA_ENTRY_TYPE = DataEntryTypeEnum.research_facilities

    INGEST_NOUN = "research facilities"
    MISSING_UNIT_REASON = "Missing unit (Centre financier)"

    CAPTION_ID = "research_facility_id"
    CAPTION_NAME = "research_facility_name"
    CAPTION_USE = "amount"
    CAPTION_UNIT = "unit_institutional_id"
    CAPTION_DATE = "date_iso"
    CAPTION_CLIENT_TYPE = "client_type"

    FUNCTION_USE = "SUM"

    USE_UNIT = "CHF"
    INTERNAL_CLIENT_TYPE = "INTERNE"

    REQUIRED_CAPTIONS: list[CaptionSpec] = [
        CaptionSpec(CAPTION_ID),
        CaptionSpec(CAPTION_NAME),
        CaptionSpec(CAPTION_USE, function=FUNCTION_USE),
        CaptionSpec(CAPTION_UNIT),
        CaptionSpec(CAPTION_DATE),
        CaptionSpec(CAPTION_CLIENT_TYPE),
    ]

    async def transform_data(
        self, raw_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        transformed: list[dict[str, Any]] = []
        year = str(self.config["year"])
        for record in raw_data:
            if record.get(self.CAPTION_CLIENT_TYPE) != self.INTERNAL_CLIENT_TYPE:
                continue
            date_iso = str(record.get(self.CAPTION_DATE) or "")
            if date_iso[:4] != year:
                continue
            facility_id = record.get(self.CAPTION_ID)
            if not facility_id or str(facility_id).strip() == "":
                continue
            facility_name = record.get(self.CAPTION_NAME)
            if not facility_name or str(facility_name).strip() == "":
                continue
            raw_use = record.get(f"{self.FUNCTION_USE}({self.CAPTION_USE})")
            if raw_use is None:
                continue
            try:
                use = -float(raw_use)
            except ValueError, TypeError:
                continue
            if use < 0:
                continue
            transformed.append(
                {
                    "unit_institutional_id": self._strip_unit_prefix(
                        record.get(self.CAPTION_UNIT)
                    ),
                    "researchfacility_id": str(facility_id).strip(),
                    "researchfacility_name": str(facility_name).strip(),
                    "use": use,
                    "use_unit": self.USE_UNIT,
                    "note": None,
                }
            )
        logger.info(
            "Research facilities transform kept %s of %s rows",
            len(transformed),
            len(raw_data),
        )
        return transformed

    def _success_status_message(self, stats: StatsDict) -> str:
        return (
            f"Processed {stats['rows_processed']} research facility records, "
            f"{stats['rows_skipped']} skipped"
        )

    def _build_data_entry(
        self, record: dict[str, Any], carbon_report_module_id: int
    ) -> DataEntry:
        return DataEntry(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=DataEntryTypeEnum.research_facilities.value,
            data={
                "researchfacility_id": record["researchfacility_id"],
                "researchfacility_name": record["researchfacility_name"],
                "use": record["use"],
                "use_unit": record["use_unit"],
                "note": record.get("note"),
            },
        )

    async def _load_data(self, data: list[dict[str, Any]]) -> dict[str, Any]:
        """Bulk-insert facility entries. Emission writes are owned by the
        runner-driven recalc chain (plan 310-D), same as the travel path.
        """
        entries = []
        for item in data:
            carbon_report_module_id = item.get("carbon_report_module_id")
            if not carbon_report_module_id:
                continue
            entries.append(self._build_data_entry(item, carbon_report_module_id))
        if not entries:
            return {"inserted": 0}
        service = DataEntryService(self.data_session)
        data_entries_response = await service.bulk_create(
            entries,
            UserRead.model_validate(self.user) if self.user else None,
            job_id=self.job_id,
            source=DataEntrySourceEnum.EXTERNAL_INTEGRATION.value,
            created_by_id=self.job_id,
        )
        await self.data_session.flush()
        return {"inserted": len(data_entries_response)}
