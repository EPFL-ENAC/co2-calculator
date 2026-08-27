"""Unit tests for the process-emissions create/update DTOs (#2025).

The CSV column name doubles as the ``data_entries.data`` storage key and
as the accepted-column set for ingestion (``_get_expected_columns_from_handlers``
reads ``create_dto.model_fields``), so the field name is a contract with
the data-description doc, not an internal detail.  These tests pin the
renamed field and the non-negative rule that guards the emission formula.
"""

import pytest
from pydantic import ValidationError

from app.modules.process_emissions import (
    ProcessEmissionsHandlerCreate,
    ProcessEmissionsHandlerUpdate,
)

_BASE = {"data_entry_type_id": 50, "carbon_report_module_id": 1}


def _create(**overrides) -> ProcessEmissionsHandlerCreate:
    payload = {**_BASE, "category": "CH4", "quantity_kg": 12.5, **overrides}
    return ProcessEmissionsHandlerCreate.model_validate(payload)


def test_create_accepts_quantity_kg_and_stores_it_under_that_key() -> None:
    dto = _create()
    assert dto.quantity_kg == 12.5
    # The mixin unflattens non-meta fields into ``data``; that dict is what
    # lands in the DB and what the emission formula reads back.
    assert dto.data["quantity_kg"] == 12.5
    assert "quantity" not in dto.data


def test_create_rejects_legacy_quantity_field() -> None:
    payload = {**_BASE, "category": "CH4", "quantity": 12.5}
    with pytest.raises(ValidationError) as exc:
        ProcessEmissionsHandlerCreate.model_validate(payload)
    assert "quantity_kg" in str(exc.value)


def test_create_requires_quantity_kg() -> None:
    payload = {**_BASE, "category": "CH4"}
    with pytest.raises(ValidationError):
        ProcessEmissionsHandlerCreate.model_validate(payload)


def test_create_rejects_negative_quantity_kg() -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        _create(quantity_kg=-1.0)


def test_update_allows_absent_quantity_kg_but_still_rejects_negative() -> None:
    assert (
        ProcessEmissionsHandlerUpdate.model_validate(
            {**_BASE, "category": "CH4"}
        ).quantity_kg
        is None
    )
    with pytest.raises(ValidationError, match="non-negative"):
        ProcessEmissionsHandlerUpdate.model_validate({**_BASE, "quantity_kg": -0.5})
