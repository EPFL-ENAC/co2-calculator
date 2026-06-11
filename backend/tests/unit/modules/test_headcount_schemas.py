"""Headcount validation permutation matrix (member + student create DTOs).

One falsifiable case per field-level rule in the ``headcount_data.csv``
contract (data-description.md → Headcount):

    name                  ✅ non-empty string (stripped)
    sius_code             ✅ within {51,52,53,54,56,57,58,59}
    user_institutional_id ✅ non-empty (doc says numbers-only, but the code
                              intentionally allows letters, e.g. "test-412424")
    fte                   ✅ float, 0 ≤ fte ≤ 1
    note                  ❌ optional

``unit_institutional_id`` is a data.csv-only column used to scope the row to
a unit at ingest; it is not part of the create DTO, so it is out of scope here.

These run the DTO directly (the same object ``validate_create`` builds for both
CSV upload and the API), so a row that fails here is a row the upload rejects.
The emission/stats chain is covered separately in
``tests/integration/services/data_ingestion/test_headcount_pg.py``.
"""

import pytest
from pydantic import ValidationError

from app.models.data_entry import DataEntryTypeEnum
from app.modules.headcount.schemas import (
    SIUS_CODE_VALUES,
    HeadCountCreate,
    HeadCountStudentCreate,
    HeadCountUpdate,
)

# Sentinel: a field set to ``_OMIT`` is dropped from the payload entirely,
# so we can exercise the "field missing" case distinctly from "field empty".
_OMIT = object()

_MEMBER_META = {
    "data_entry_type_id": DataEntryTypeEnum.member.value,
    "carbon_report_module_id": 1,
}
_STUDENT_META = {
    "data_entry_type_id": DataEntryTypeEnum.student.value,
    "carbon_report_module_id": 1,
}


def _member(**overrides) -> dict:
    payload = {
        **_MEMBER_META,
        "name": "Alice Smith",
        "sius_code": "51",
        "user_institutional_id": "123456",
        "fte": 0.8,
    }
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not _OMIT}


def _student(**overrides) -> dict:
    payload = {**_STUDENT_META, "fte": 0.5}
    payload.update(overrides)
    return {k: v for k, v in payload.items() if v is not _OMIT}


# ---------------------------------------------------------------------------
# Member — valid (passing) permutations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_member(), id="baseline"),
        pytest.param(_member(fte=0.0), id="fte-lower-bound"),
        pytest.param(_member(fte=1.0), id="fte-upper-bound"),
        pytest.param(_member(fte=0.05), id="fte-doc-example"),
        pytest.param(_member(fte="0.75"), id="fte-numeric-string-coerced"),
        pytest.param(_member(note="seconded 50%"), id="note-present"),
        pytest.param(_member(note=_OMIT), id="note-omitted"),
        pytest.param(_member(name="  Bob Jones  "), id="name-stripped"),
        # Doc says "numbers only" but the schema deliberately allows letters.
        pytest.param(_member(user_institutional_id="test-412424"), id="uid-letters"),
        *[
            pytest.param(_member(sius_code=code), id=f"sius-{code}")
            for code in sorted(SIUS_CODE_VALUES)
        ],
    ],
)
def test_headcount_member_valid(payload: dict) -> None:
    item = HeadCountCreate.model_validate(payload)
    assert item.sius_code in SIUS_CODE_VALUES
    assert 0 <= item.fte <= 1


def test_headcount_member_strips_name_and_uid() -> None:
    item = HeadCountCreate.model_validate(
        _member(name="  Bob Jones  ", user_institutional_id=" 123456 ")
    )
    assert item.name == "Bob Jones"
    assert item.user_institutional_id == "123456"


# ---------------------------------------------------------------------------
# Member — invalid (failing) permutations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_member(name=_OMIT), id="name-missing"),
        pytest.param(_member(name=""), id="name-empty"),
        pytest.param(_member(name="   "), id="name-whitespace"),
        pytest.param(_member(sius_code=_OMIT), id="sius-missing"),
        pytest.param(_member(sius_code="55"), id="sius-not-in-set"),
        pytest.param(_member(sius_code="60"), id="sius-out-of-range"),
        pytest.param(_member(sius_code="professor"), id="sius-non-numeric"),
        pytest.param(_member(user_institutional_id=_OMIT), id="uid-missing"),
        pytest.param(_member(user_institutional_id=""), id="uid-empty"),
        pytest.param(_member(user_institutional_id="   "), id="uid-whitespace"),
        pytest.param(_member(fte=_OMIT), id="fte-missing"),
        pytest.param(_member(fte=1.5), id="fte-above-one"),
        pytest.param(_member(fte=-0.1), id="fte-negative"),
        pytest.param(_member(fte="not-a-number"), id="fte-uncoercible"),
    ],
)
def test_headcount_member_invalid(payload: dict) -> None:
    with pytest.raises(ValidationError):
        HeadCountCreate.model_validate(payload)


# ---------------------------------------------------------------------------
# Student — fte is the only field; non-negative, no documented upper bound
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_student(fte=0.5), id="baseline"),
        pytest.param(_student(fte=0.0), id="fte-zero"),
        pytest.param(_student(fte="0.5"), id="fte-numeric-string-coerced"),
        # NOTE: student fte has no upper-bound check (unlike member's ≤1).
        # If that asymmetry is unintended, this case flags it.
        pytest.param(_student(fte=2.0), id="fte-above-one-allowed"),
    ],
)
def test_headcount_student_valid(payload: dict) -> None:
    item = HeadCountStudentCreate.model_validate(payload)
    assert item.fte >= 0


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param(_student(fte=_OMIT), id="fte-missing"),
        pytest.param(_student(fte=-0.1), id="fte-negative"),
        pytest.param(_student(fte="not-a-number"), id="fte-uncoercible"),
    ],
)
def test_headcount_student_invalid(payload: dict) -> None:
    with pytest.raises(ValidationError):
        HeadCountStudentCreate.model_validate(payload)


# ---------------------------------------------------------------------------
# Update DTO — fields optional, but constraints still enforced when present
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({**_MEMBER_META, "sius_code": "54"}, id="sius-only"),
        pytest.param({**_MEMBER_META, "fte": 0.9}, id="fte-only"),
        pytest.param({**_MEMBER_META}, id="nothing-to-update"),
    ],
)
def test_headcount_update_valid(payload: dict) -> None:
    HeadCountUpdate.model_validate(payload)


@pytest.mark.parametrize(
    "payload",
    [
        pytest.param({**_MEMBER_META, "sius_code": "invalid"}, id="sius-invalid"),
        pytest.param({**_MEMBER_META, "fte": 1.5}, id="fte-above-one"),
        pytest.param({**_MEMBER_META, "fte": -1}, id="fte-negative"),
    ],
)
def test_headcount_update_invalid(payload: dict) -> None:
    with pytest.raises(ValidationError):
        HeadCountUpdate.model_validate(payload)
