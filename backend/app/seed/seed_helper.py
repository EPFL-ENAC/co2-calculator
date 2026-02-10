from typing import Dict, Optional

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.models.module_type import ModuleTypeEnum
from app.schemas.carbon_report import CarbonReportCreate
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService
from app.services.factor_service import FactorService
from app.services.unit_service import UnitService

logger = get_logger(__name__)
settings = get_settings()
versionapi = settings.FORMULA_VERSION_SHA256_SHORT


async def get_carbon_report_module_id(
    unit_provider_code: str, year: int, module_type_id: ModuleTypeEnum
) -> int:
    """Generate real carbon_report_module_id based on unit and year."""
    # Get unit by provider code to find unit_id
    current_module_type_id = module_type_id.value
    async with SessionLocal() as session:
        service = CarbonReportService(session)
        unit_service = UnitService(session)
        unit = await unit_service.get_by_provider_code(unit_provider_code)
        if not unit:
            raise ValueError(f"Unit with provider code {unit_provider_code} not found")
        # Get or create carbon report for unit and year
        carbon_report = await service.get_by_unit_and_year(unit_id=unit.id, year=year)
        if not carbon_report:
            # create carbon report if not exists
            logger.info(
                f"Creating carbon report for unit {unit_provider_code} year {year}"
            )
            carbon_report = await service.create(
                data=CarbonReportCreate(unit_id=unit.id, year=year)
            )
            if not carbon_report:
                raise ValueError(
                    f"Could not create carbon report for unit "
                    f"{unit_provider_code} year {year}"
                )
        # Get carbon_report_module_id for module type
        module_service = CarbonReportModuleService(session)
        # print(carbon_report)
        carbon_report_module = await module_service.get_module(
            carbon_report_id=carbon_report.id,
            module_type_id=current_module_type_id,
        )
        # print(carbon_report_module)
        if not carbon_report_module:
            raise ValueError(
                f"Could not find carbon report module for unit "
                f"{unit_provider_code} year {year} "
                f"and module type {current_module_type_id}"
            )
        if carbon_report_module.id is None:
            raise ValueError(
                f"Carbon report module ID is None for unit {unit_provider_code}"
            )
        return carbon_report_module.id


async def load_factors_map(
    session: AsyncSession, data_entry_type: DataEntryTypeEnum
) -> Dict[str, Factor]:
    """Load factors from database into a lookup dictionary."""
    logger.info("Loading factors from database...")

    service = FactorService(session)
    factors: list[Factor] = await service.list_by_data_entry_type(data_entry_type)
    factors_map: Dict[str, Factor] = {}

    for pf in factors:
        # Strategy 1: Full match with subkind
        if pf.classification:
            key_full = (
                f"{pf.data_entry_type_id}:"
                f"{pf.classification.get('kind', '').lower()}:"
                f"{(pf.classification.get('subkind') or '').lower()}"
            )
            factors_map[key_full] = pf

        # Strategy 2: Match without subkind (fallback)
        key_kind = (
            f"{pf.data_entry_type_id}:{pf.classification.get('kind', '').lower()}"
        )
        if key_kind not in factors_map:
            factors_map[key_kind] = pf

    # logger.info(f"Loaded {len(factors)} factors with {len(factors_map)} lookup keys")
    return factors_map


def normalize_kind(kind: str) -> str:
    """Normalize kind for case-insensitive matching."""
    # Class names are mostly unique in table_power.csv
    # Just normalize to lowercase for matching
    return kind.lower().strip()


def is_in_factors_map(
    kind: str,
    subkind: Optional[str],
    factors_map: Dict[str, Factor],
    *,
    require_subkind: bool = False,
) -> bool:
    normalized_kind_value = normalize_kind(kind)
    subkind_value = normalize_kind(subkind) if subkind else None

    if require_subkind and not subkind_value:
        return False

    if subkind_value:
        pattern = f":{normalized_kind_value}:{subkind_value}"
        return any(k.endswith(pattern) for k in factors_map.keys())

    # kind-only check
    kind_pattern = f":{normalized_kind_value}"
    return any(k.endswith(kind_pattern) for k in factors_map.keys())


def lookup_factor(
    kind: str,
    subkind: Optional[str],
    factors_map: Dict[str, Factor],
) -> Optional[Factor]:
    """
    Lookup factor for data_entry by kind only.

    Returns None if no match found OR if multiple matches exist (ambiguous).

    Logic:
    - If 0 matches: Returns None (no factor available)
    - If 1 match: Returns the factor (unambiguous)
    - If >1 matches: Returns first match for testing, logs warning (sub-kind required)
    """
    normalized_kind_value = normalize_kind(kind)
    subkind_value = normalize_kind(subkind) if subkind else None

    # Find ALL matching factors across all submodul
    if subkind_value is None:
        subkind_value = ""
    keys = [
        k for k in factors_map.keys() if k.__contains__(f":{normalized_kind_value}:")
    ]
    search_pattern = f":{normalized_kind_value}:{subkind_value}"
    matches = [pf for pf in keys if pf.endswith(search_pattern)]
    if len(matches) == 0:
        # No power factor found
        return None
    elif len(matches) == 1:
        # Unambiguous match
        return factors_map[matches[0]]
    else:
        # Ambiguous - multiple matches found
        logger.warning(
            f"Ambiguous factor lookup for kind '{kind}' "
            f"and subkind '{subkind}': "
            f"{len(matches)} matches found. "
            f"Sub-kind selection required for accurate matching."
        )
        return factors_map[matches[0]]
