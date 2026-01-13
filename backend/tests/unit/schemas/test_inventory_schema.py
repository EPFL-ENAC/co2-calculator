import pytest
from pydantic import ValidationError

from app.core.constants import ModuleStatus
from app.schemas.inventory import (
    InventoryCreate,
    InventoryModuleCreate,
    InventoryModuleRead,
    InventoryModuleUpdate,
    InventoryRead,
)


def test_inventory_create_schema():
    data = {"year": 2025, "unit_id": "unit-123"}
    obj = InventoryCreate(**data)
    assert obj.year == 2025
    assert obj.unit_id == "unit-123"


def test_inventory_read_schema():
    data = {"id": 1, "year": 2025, "unit_id": "unit-123"}
    obj = InventoryRead(**data)
    assert obj.id == 1
    assert obj.year == 2025
    assert obj.unit_id == "unit-123"


def test_inventory_module_create_schema():
    data = {"module_type_id": 1, "status": ModuleStatus.IN_PROGRESS}
    obj = InventoryModuleCreate(**data)
    assert obj.module_type_id == 1
    assert obj.status == ModuleStatus.IN_PROGRESS


def test_inventory_module_create_default_status():
    data = {"module_type_id": 1}
    obj = InventoryModuleCreate(**data)
    assert obj.status == ModuleStatus.NOT_STARTED


def test_inventory_module_read_schema():
    data = {
        "id": 2,
        "inventory_id": 1,
        "module_type_id": 1,
        "status": ModuleStatus.VALIDATED,
    }
    obj = InventoryModuleRead(**data)
    assert obj.id == 2
    assert obj.inventory_id == 1
    assert obj.module_type_id == 1
    assert obj.status == ModuleStatus.VALIDATED


def test_inventory_module_update_schema():
    data = {"status": ModuleStatus.IN_PROGRESS}
    obj = InventoryModuleUpdate(**data)
    assert obj.status == ModuleStatus.IN_PROGRESS


def test_inventory_module_update_validation():
    # Status must be between 0 and 2
    with pytest.raises(ValidationError):
        InventoryModuleUpdate(status=5)
    with pytest.raises(ValidationError):
        InventoryModuleUpdate(status=-1)


def test_inventory_create_schema_validation():
    with pytest.raises(ValidationError):
        InventoryCreate(year="not_a_year", unit_id="unit-123")
    with pytest.raises(ValidationError):
        InventoryCreate(year=2025, unit_id=None)
