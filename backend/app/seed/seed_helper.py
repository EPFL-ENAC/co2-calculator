from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.module_type import ModuleTypeEnum
from app.schemas.carbon_report import CarbonReportCreate
from app.services.carbon_report_module_service import CarbonReportModuleService
from app.services.carbon_report_service import CarbonReportService
from app.services.unit_service import UnitService

logger = get_logger(__name__)
settings = get_settings()
versionapi = settings.FORMULA_VERSION_SHA256_SHORT


async def get_carbon_report_module_id(unit_provider_code: str, year: int) -> int:
    """Generate real carbon_report_module_id based on unit and year."""
    # Get unit by provider code to find unit_id
    current_module_type_id = ModuleTypeEnum.equipment_electric_consumption.value
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
        # Get carbon_report_module_id for equipment module type
        module_service = CarbonReportModuleService(session)
        carbon_report_module = await module_service.get_module(
            carbon_report_id=carbon_report.id,
            module_type_id=current_module_type_id,
        )
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
