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

    # Routine exclusions: external billing is never ours, and a year the
    # datasource has not published yet is a "come back later", not a fault.
    # Everything else means the rows do not look the way we expect (#2007).
    EXPECTED_EMPTY_DROP_REASONS = frozenset({"client_type", "year"})

    DROP_REASON_MESSAGES = {
        "client_type": (
            "{count} row(s) are not internal billing "
            f"({CAPTION_CLIENT_TYPE} is not {INTERNAL_CLIENT_TYPE})"
        ),
        "year": "{count} row(s) are dated a different year than {year}",
        "blank_id": f"{{count}} row(s) have no {CAPTION_ID}",
        "blank_name": f"{{count}} row(s) have no {CAPTION_NAME}",
        "no_amount": f"{{count}} row(s) have no {FUNCTION_USE}({CAPTION_USE})",
        "amount_not_numeric": (
            f"{{count}} row(s) have a non-numeric {FUNCTION_USE}({CAPTION_USE})"
        ),
        "amount_positive": (
            f"{{count}} row(s) have a positive {FUNCTION_USE}({CAPTION_USE}) "
            "— internal billing is recorded negative"
        ),
    }

    async def transform_data(
        self, raw_data: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        year = str(self.config["year"])
        monthly_rows: list[dict[str, Any]] = []
        for record in raw_data:
            if record.get(self.CAPTION_CLIENT_TYPE) != self.INTERNAL_CLIENT_TYPE:
                self.drop_reasons["client_type"] += 1
                continue
            date_iso = str(record.get(self.CAPTION_DATE) or "")
            if date_iso[:4] != year:
                self.drop_reasons["year"] += 1
                continue
            facility_id = record.get(self.CAPTION_ID)
            if not facility_id or str(facility_id).strip() == "":
                self.drop_reasons["blank_id"] += 1
                continue
            facility_name = record.get(self.CAPTION_NAME)
            if not facility_name or str(facility_name).strip() == "":
                self.drop_reasons["blank_name"] += 1
                continue
            raw_use = record.get(f"{self.FUNCTION_USE}({self.CAPTION_USE})")
            if raw_use is None:
                self.drop_reasons["no_amount"] += 1
                continue
            try:
                use = -float(raw_use)
            except ValueError, TypeError:
                self.drop_reasons["amount_not_numeric"] += 1
                continue
            if use < 0:
                self.drop_reasons["amount_positive"] += 1
                continue
            monthly_rows.append(
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

        # date_iso is a string-typed calculated field: VDS rejects a YEAR/
        # TRUNC_YEAR function on it ("wrong type"), and rejects filtering on
        # it unless it's also an output field ("field not defined"). So VDS
        # returns SUM(amount) grouped at date_iso's native (month) grain —
        # collapse those monthly rows into one annual total per (facility, unit)
        # here instead (facility IDs are only unique within a unit).
        yearly_totals: dict[tuple[str, str | None], dict[str, Any]] = {}
        for row in monthly_rows:
            key = (row["researchfacility_id"], row["unit_institutional_id"])
            existing = yearly_totals.get(key)
            if existing is None:
                yearly_totals[key] = dict(row)
            else:
                existing["use"] += row["use"]
        transformed = list(yearly_totals.values())

        logger.info(
            "Research facilities transform kept %s of %s rows%s "
            "(aggregated into %s yearly totals)",
            len(monthly_rows),
            len(raw_data),
            f" — dropped: {self._describe_drops()}" if self.drop_reasons else "",
            len(transformed),
        )
        return transformed

    def _empty_transform_is_routine(self, raw_data: list[dict[str, Any]]) -> bool:
        """Beyond the reason names, prove the datasource still looks the way
        we expect before trusting "no INTERNE rows this year" (#2457):

        - at least one raw row is billed to an internal client — proves the
          ``client_type`` field/value/casing still matches, so an all-rows
          "client_type" drop means the field genuinely changed, not that we
          stopped recognizing it;
        - every one of those internal rows has a 4-digit numeric year prefix
          on ``date_iso`` — proves the date field's format hasn't drifted,
          so an all-rows "year" drop means the year genuinely isn't there.

        Otherwise a casing or date-format change upstream would tag every
        row under one of these "expected" reasons and silently wipe the
        year's data on the next sync.
        """
        if not super()._empty_transform_is_routine(raw_data):
            return False
        # ponytail: existence proof only — a mixed-casing datasource (some
        # "INTERNE", most "Interne") still passes. Tighten to a ratio if
        # mixed casing ever shows up in practice.
        internal_rows = [
            row
            for row in raw_data
            if row.get(self.CAPTION_CLIENT_TYPE) == self.INTERNAL_CLIENT_TYPE
        ]
        if not internal_rows:
            return False
        return all(
            self._looks_like_year_prefix(row.get(self.CAPTION_DATE))
            for row in internal_rows
        )

    @staticmethod
    def _looks_like_year_prefix(date_value: Any) -> bool:
        """True if ``date_value`` starts with a plausible 4-digit year —
        guards against a date-format drift (e.g. epoch millis, DD/MM/YYYY)
        that would still slice to 4 digits but isn't a year.
        """
        prefix = str(date_value or "")[:4]
        return len(prefix) == 4 and prefix.isdigit() and 1900 <= int(prefix) <= 2100

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
