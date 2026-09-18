"""Shared normalized string types for factor-resolution join keys (#1489).

Factor resolution compares ``factor.classification[k]`` to ``entry.data[k]``
with exact string equality (``factor_resolver._build_maps``), and the factor
upsert keys on ``(classification::text)`` — so the two sides must normalize
identically or the same real-world value produces duplicate factor rows and
silent resolution misses. Apply these aliases symmetrically: every field that
participates in a factor lookup carries the same alias on the
``*FactorCreate/Update`` and the ``*HandlerCreate/Update`` DTO.

Canonical forms (agreed on #1489):
- closed vocabularies (currency, cabin_class): strip + lower
- country codes: strip + upper, with the ``RoW`` sentinel kept as-is
- free text (names, codes, ids): strip only — case carries meaning there
"""

import re
from typing import Annotated, Any

from pydantic import BeforeValidator, StringConstraints

# The mixed-case "rest of world" sentinel used by factor CSVs and the UI.
ROW_COUNTRY_CODE = "RoW"

_INT_WITH_TRAILING_ZEROS = re.compile(r"^(\d+)\.0*$")


def _normalize_country_code(v: Any) -> Any:
    if not isinstance(v, str):
        return v
    stripped = v.strip()
    if stripped.lower() == ROW_COUNTRY_CODE.lower():
        return ROW_COUNTRY_CODE
    return stripped.upper()


def _coerce_numeric_identifier(v: Any) -> Any:
    # Spreadsheet-exported id columns arrive as 1, 1.0 or "1.0" — all mean
    # the id "1". String forms only lose whitespace and a trailing ".0" so
    # zero-padded non-numeric ids pass through untouched. Stripping happens
    # here, not via StringConstraints: pydantic checks min_length before a
    # combined BeforeValidator+strip_whitespace annotation strips.
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else str(v)
    if isinstance(v, str):
        stripped = v.strip()
        match = _INT_WITH_TRAILING_ZEROS.match(stripped)
        return match.group(1) if match else stripped
    return v


def _blank_to_none(v: Any) -> Any:
    if isinstance(v, str):
        stripped = v.strip()
        return stripped if stripped else None
    return v


CurrencyCode = Annotated[
    str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1)
]

CountryCode = Annotated[
    str, BeforeValidator(_normalize_country_code), StringConstraints(min_length=1)
]

ClassificationKey = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1)
]

# Optional join key where blank means absent: both sides store None, never "".
OptionalClassificationKey = Annotated[str | None, BeforeValidator(_blank_to_none)]

# Join key that may arrive as a spreadsheet number (researchfacility_id).
IdentifierKey = Annotated[
    str,
    BeforeValidator(_coerce_numeric_identifier),
    StringConstraints(min_length=1),
]
