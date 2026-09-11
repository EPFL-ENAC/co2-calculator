"""#2700 — a model-level validation error must read as a row error, not crash.

A research-facilities upload skipped a row with "Row processing error: tuple
index out of range": ``_format_pydantic_validation_error`` indexed
``err["loc"][-1]``, and a ``@model_validator`` error carries an empty ``loc``.
"""

import pytest
from pydantic import ValidationError

from app.modules.research_facilities.data_entries import (
    ResearchFacilitiesCommonHandlerCreate,
)
from app.services.data_ingestion.base_csv_provider import (
    _format_pydantic_validation_error,
)


def test_model_level_error_formats_without_field_name():
    with pytest.raises(ValidationError) as exc_info:
        ResearchFacilitiesCommonHandlerCreate.model_validate(
            {
                "data_entry_type_id": 70,
                "carbon_report_module_id": 1,
                "researchfacility_id": "0619",
                "researchfacility_name": "PTCB",
                "use": 15387.77,
                "use_unit": "hours",
            }
        )

    message = _format_pydantic_validation_error(exc_info.value)

    assert "use must be at most" in message
    # Whole-row input never lands in job metadata (headcount rows are personal data).
    assert "PTCB" not in message


def test_field_level_error_keeps_field_and_value():
    with pytest.raises(ValidationError) as exc_info:
        ResearchFacilitiesCommonHandlerCreate.model_validate(
            {
                "data_entry_type_id": 70,
                "carbon_report_module_id": 1,
                "researchfacility_id": "0619",
                "researchfacility_name": "PTCB",
                "use": "abc",
                "use_unit": "hours",
            }
        )

    message = _format_pydantic_validation_error(exc_info.value)

    assert message.startswith("use: ")
    assert "(got 'abc')" in message
