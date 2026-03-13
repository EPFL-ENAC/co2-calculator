import pytest
from pydantic import ValidationError

from app.models.data_entry import DataEntryTypeEnum
from app.modules.headcount.schemas import HeadCountCreate, HeadCountUpdate


def _base_create_payload() -> dict:
    return {
        "data_entry_type_id": DataEntryTypeEnum.member.value,
        "carbon_report_module_id": 1,
    }


def test_headcount_create_accepts_valid_position_category() -> None:
    item = HeadCountCreate(
        **_base_create_payload(),
        name="Alice",
        position_category="professor",
        user_institutional_id="12345",
    )
    assert item.position_category == "professor"


def test_headcount_create_rejects_invalid_position_category() -> None:
    with pytest.raises(ValidationError):
        HeadCountCreate(
            **_base_create_payload(),
            name="Alice",
            position_category="invalid_category",
        )


def test_headcount_update_accepts_valid_position_category() -> None:
    item = HeadCountUpdate(**_base_create_payload(), position_category="student")
    assert item.position_category == "student"


def test_headcount_update_rejects_invalid_position_category() -> None:
    with pytest.raises(ValidationError):
        HeadCountUpdate(
            **_base_create_payload(),
            position_category="invalid_category",
        )


def test_headcount_create_accepts_numeric_user_institutional_id() -> None:
    item = HeadCountCreate(
        **_base_create_payload(),
        name="Alice",
        user_institutional_id="12345",
    )
    assert item.user_institutional_id == "12345"


def test_headcount_create_strips_whitespace_in_user_institutional_id() -> None:
    item = HeadCountCreate(
        **_base_create_payload(),
        name="Alice",
        user_institutional_id=" 12345 ",
    )
    assert item.user_institutional_id == "12345"


def test_headcount_create_rejects_non_digit_user_institutional_id() -> None:
    with pytest.raises(ValidationError):
        HeadCountCreate(
            **_base_create_payload(),
            name="Alice",
            user_institutional_id="12A45",
        )
