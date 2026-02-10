import pytest
from pydantic import ValidationError

from app.core.constants import ModuleStatus
from app.schemas.carbon_report import (
    CarbonReportCreate,
    CarbonReportModuleCreate,
    CarbonReportModuleRead,
    CarbonReportModuleUpdate,
    CarbonReportRead,
)


def test_carbon_report_create_schema():
    data = {"year": 2025, "unit_id": 1}
    obj = CarbonReportCreate(**data)
    assert obj.year == 2025
    assert obj.unit_id == 1


def test_carbon_report_read_schema():
    data = {"id": 1, "year": 2025, "unit_id": 1}
    obj = CarbonReportRead(**data)
    assert obj.id == 1
    assert obj.year == 2025
    assert obj.unit_id == 1


def test_carbon_report_module_create_schema():
    data = {"module_type_id": 1, "status": ModuleStatus.IN_PROGRESS}
    obj = CarbonReportModuleCreate(**data)
    assert obj.module_type_id == 1
    assert obj.status == ModuleStatus.IN_PROGRESS


def test_carbon_report_module_create_default_status():
    data = {"module_type_id": 1}
    obj = CarbonReportModuleCreate(**data)
    assert obj.status == ModuleStatus.NOT_STARTED


def test_carbon_report_module_read_schema():
    data = {
        "id": 2,
        "carbon_report_id": 1,
        "module_type_id": 1,
        "status": ModuleStatus.VALIDATED,
    }
    obj = CarbonReportModuleRead(**data)
    assert obj.id == 2
    assert obj.carbon_report_id == 1
    assert obj.module_type_id == 1
    assert obj.status == ModuleStatus.VALIDATED


def test_carbon_report_module_update_schema():
    data = {"status": ModuleStatus.IN_PROGRESS}
    obj = CarbonReportModuleUpdate(**data)
    assert obj.status == ModuleStatus.IN_PROGRESS


def test_carbon_report_module_update_validation():
    # Status must be between 0 and 2
    with pytest.raises(ValidationError):
        CarbonReportModuleUpdate(status=5)
    with pytest.raises(ValidationError):
        CarbonReportModuleUpdate(status=-1)


def test_carbon_report_create_schema_validation():
    with pytest.raises(ValidationError):
        CarbonReportCreate(year="not_a_year", unit_id="unit-123")
    with pytest.raises(ValidationError):
        CarbonReportCreate(year=2025, unit_id=None)
