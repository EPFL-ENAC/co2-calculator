"""Energy combustion entry DTOs carry the unit (#2591 D-6).

The doc always listed ``unit`` as a mandatory data column; the DTO dropped
it, so the column was silently ignored and the row was priced per whatever
unit the factor happened to use. The entry now carries its unit and the
entry-time check (``factor_resolver.unresolved_reason``) rejects a
mismatch with the factor.
"""

import pytest
from pydantic import ValidationError

from app.modules.buildings.data_entries import (
    EnergyCombustionHandlerCreate,
    EnergyCombustionHandlerUpdate,
)


def _payload(**overrides):
    payload = {
        "data_entry_type_id": 31,
        "carbon_report_module_id": 1,
        "name": "pellets",
        "unit": " kg ",
        "quantity": 12.0,
    }
    payload.update(overrides)
    return payload


def test_create_requires_unit_and_strips_it() -> None:
    dto = EnergyCombustionHandlerCreate.model_validate(_payload())
    assert dto.unit == "kg"
    assert dto.data["unit"] == "kg"
    with pytest.raises(ValidationError, match="unit"):
        EnergyCombustionHandlerCreate.model_validate(_payload(unit=None))


def test_update_unit_optional_but_never_blank() -> None:
    meta = {"data_entry_type_id": 31, "carbon_report_module_id": 1}
    dto = EnergyCombustionHandlerUpdate.model_validate({**meta, "quantity": 1.0})
    assert dto.unit is None
    with pytest.raises(ValidationError):
        EnergyCombustionHandlerUpdate.model_validate({**meta, "unit": "   "})
