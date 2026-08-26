"""#2404 — every handler ``kind_field`` must have a factor-resolution index.

``_resolved_factor_id`` (``data_entry_repo.py``) matches
``factors.classification->>kind_field`` against each entry, per row. Without
a matching partial expression index that lookup is a filtered scan over the
det's whole factor set for every row of a submodule page — measured at
2.08 ms/row against 1 219 candidate factors, 10× worse than indexed.

``FACTOR_RESOLUTION_INDEX_KEYS`` is a hand-maintained list (deriving it from
the handler registry would create a models → schemas import cycle). This
test is what keeps it honest: registering a handler with a new
``kind_field`` fails here instead of silently reintroducing the scan. It
already caught one — ``purchase_category`` is declared assignment-style in
``modules_planner/purchase/handlers.py`` and the grep census that first
built the list missed it.

Travel and headcount dets are exempt: ``get_submodule_data`` never routes
them through ``_resolved_factor_id`` (their factor display comes from the
computed emission rows), mirroring its own ``is_travel_entry`` /
``is_headcount_entry`` exclusions.
"""

import app.modules  # noqa: F401  — registers all module handlers
import app.modules_planner  # noqa: F401  — registers planner handlers
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import FACTOR_RESOLUTION_INDEX_KEYS, Factor
from app.schemas.data_entry import MODULE_HANDLERS

# Dets get_submodule_data excludes from SQL factor resolution.
_EXEMPT_DETS = {
    DataEntryTypeEnum.plane,
    DataEntryTypeEnum.train,
    DataEntryTypeEnum.member,
    DataEntryTypeEnum.student,
    DataEntryTypeEnum.planner_headcount,
}


def test_every_resolving_handler_kind_field_is_indexed():
    unindexed = {
        (det.name, handler.kind_field)
        for det, handler in MODULE_HANDLERS.items()
        if det not in _EXEMPT_DETS
        and handler.kind_field
        and handler.kind_field not in FACTOR_RESOLUTION_INDEX_KEYS
    }
    assert not unindexed, (
        f"handlers whose kind_field has no ix_factors_res_* index: {unindexed} — "
        "add the key to FACTOR_RESOLUTION_INDEX_KEYS and ship the index in a "
        "migration, or the submodule listing pays a per-row factor scan again "
        "(#2404)"
    )


def test_index_set_matches_declared_keys():
    """The model's __table_args__ must carry exactly one index per key —
    a key added to the list without its Index (or vice versa) is a silent
    no-op in production.
    """
    declared = {
        idx.name
        for idx in Factor.__table_args__
        if getattr(idx, "name", "").startswith("ix_factors_res_")
    }
    expected = {f"ix_factors_res_{key}" for key in FACTOR_RESOLUTION_INDEX_KEYS}
    assert declared == expected
