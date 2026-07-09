"""Headcount members Tableau API provider (#1552).

Pulls member rows (name, SCIPER, SIUS, FTE, unit) from the headcount
Tableau datasource and persists them as ``member`` data entries.

Privacy (A09): headcount rows are personal data. Never log row contents —
counts and unit codes only.
"""

from typing import Any, Dict, List

from app.core.logging import get_logger
from app.models.connector import ConnectorType
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.schemas.user import UserRead
from app.services.data_entry_service import DataEntryService
from app.services.data_ingestion.api_providers.base_tableau_api_provider import (
    BaseTableauApiProvider,
    StatsDict,
)

logger = get_logger(__name__)


class HeadcountMembersApiProvider(BaseTableauApiProvider):
    """Headcount (members) provider backed by the EPFL Tableau connection.

    Credentials + datasource LUID come from the DB via the base class; this
    subclass owns only the member-specific transform/load.
    """

    CONNECTOR = ConnectorType.EPFL_TABLEAU
    MODULE_TYPE = ModuleTypeEnum.headcount
    DATA_ENTRY_TYPE = DataEntryTypeEnum.member

    INGEST_NOUN = "headcount"
    MISSING_UNIT_REASON = "Missing unit (Centre financier)"

    # Placeholder captions — fill from read-metadata against the headcount
    # connector_luid once it is set via the API connect form. Captions are
    # validated against read-metadata at fetch time so a rename upstream
    # fails loud instead of silently dropping a column.
    CAPTION_NAME = "Name"
    CAPTION_SCIPER = "SCIPER"
    CAPTION_SIUS = "SIUS"
    CAPTION_FTE = "FTE"
    CAPTION_UNIT = "Centre financier"

    REQUIRED_CAPTIONS: list[str] = [
        CAPTION_NAME,
        CAPTION_SCIPER,
        CAPTION_SIUS,
        CAPTION_FTE,
        CAPTION_UNIT,
    ]

    async def transform_data(
        self, raw_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        transformed: List[Dict[str, Any]] = []
        for record in raw_data:
            sciper = record.get(self.CAPTION_SCIPER)
            if not sciper or str(sciper).strip() == "":
                continue
            raw_fte = record.get(self.CAPTION_FTE)
            if raw_fte is None:
                continue
            try:
                fte = float(raw_fte)
            except (ValueError, TypeError):
                continue
            transformed.append(
                {
                    "unit_institutional_id": self._strip_unit_prefix(
                        record.get(self.CAPTION_UNIT)
                    ),
                    "user_institutional_id": str(sciper).strip(),
                    "name": record.get(self.CAPTION_NAME) or "",
                    "sius_code": str(record.get(self.CAPTION_SIUS) or ""),
                    "fte": fte,
                    "note": None,
                }
            )
        # Personal data: log counts only, never row contents (A09).
        logger.info(
            "Headcount transform kept %s of %s rows", len(transformed), len(raw_data)
        )
        return transformed

    def _success_status_message(self, stats: StatsDict) -> str:
        return (
            f"Processed {stats['rows_processed']} member records, "
            f"{stats['rows_skipped']} skipped"
        )

    def _build_data_entry(
        self, record: Dict[str, Any], carbon_report_module_id: int
    ) -> DataEntry:
        # Persist exactly the member payload (matches HeadCountCreate);
        # routing fields (unit_institutional_id) stay out of the JSON.
        return DataEntry(
            carbon_report_module_id=carbon_report_module_id,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            data={
                "name": record["name"],
                "sius_code": record["sius_code"],
                "user_institutional_id": record["user_institutional_id"],
                "fte": record["fte"],
                "note": record.get("note"),
            },
        )

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Bulk-insert member entries. Emission writes are owned by the
        runner-driven recalc chain (plan 310-D), same as the travel path."""
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
