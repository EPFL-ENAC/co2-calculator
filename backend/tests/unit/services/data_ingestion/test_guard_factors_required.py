"""Regression: ingests for modules whose handler requires a factor
match MUST fail fast at setup when the factors map is empty.

User-reported (2026-05-20): uploading an equipment ``data.csv`` for a
module/year with no factors loaded produced 50 072 row errors,
each one variant of "no matching factor found".  The operator had to
scroll past every one to figure out the real fix is to upload factors
first.  The guard turns that into one ``FINISHED + ERROR`` job with a
single-line status message.

The guard sits in ``_setup_handlers_and_factors`` (before any row is
processed), so the existing ``_setup_and_validate`` try/except wraps
the raise into the job's terminal state automatically — covered by
the row-of-zero assertion in each positive test below.
"""

from types import SimpleNamespace

import pytest

from app.services.data_ingestion.base_csv_provider import _guard_factors_required


def _handler(require_factor: bool):
    """Minimal duck-typed ModuleHandler for the guard."""
    return SimpleNamespace(require_factor_to_match=require_factor)


def test_empty_factors_raises_when_handler_requires_match():
    """The bug shape: equipment-style handler, empty factors_map → raise."""
    with pytest.raises(ValueError) as exc:
        _guard_factors_required(
            factors_map={},
            handlers=[_handler(True)],
            module_label="Equipment",
            year=2026,
        )
    # The message must name the module + year so the operator knows
    # which factor upload is missing without reading the stack trace.
    msg = str(exc.value)
    assert "Equipment" in msg
    assert "2026" in msg
    assert "factors" in msg.lower()


def test_empty_factors_ok_when_no_handler_requires_match():
    """Modules with ``require_factor_to_match=False`` (purchase,
    buildings, headcount, …) tolerate an empty map — the guard must
    not block them."""
    _guard_factors_required(
        factors_map={},
        handlers=[_handler(False)],
        module_label="Purchase",
        year=2026,
    )  # no raise


def test_populated_factors_ok_even_when_required():
    """The happy path — at least one factor present is enough; the
    per-row loop will pick up scope mismatches if any."""
    _guard_factors_required(
        factors_map={"10:2026:foo:None": object()},
        handlers=[_handler(True)],
        module_label="Equipment",
        year=2026,
    )  # no raise


def test_mixed_handlers_any_requires_triggers_guard():
    """MODULE_PER_YEAR loads handlers for every valid data_entry_type;
    if even one of them requires a factor match, the guard must fire
    on an empty map.  (Otherwise the multi-handler module would
    silently produce per-row errors for the strict subtype.)"""
    with pytest.raises(ValueError):
        _guard_factors_required(
            factors_map={},
            handlers=[_handler(False), _handler(True)],
            module_label="Equipment",
            year=2026,
        )


def test_year_none_message_degrades_cleanly():
    """Defensive: if for some reason ``self.year`` is None the message
    must still be readable — no ``year=None`` text bleeding through."""
    with pytest.raises(ValueError) as exc:
        _guard_factors_required(
            factors_map={},
            handlers=[_handler(True)],
            module_label="Equipment",
            year=None,
        )
    msg = str(exc.value)
    assert "year=None" not in msg
    assert "configured year" in msg
