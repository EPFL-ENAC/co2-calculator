"""Guards for the #2527 Phase A dedup split, and the order Phase B must follow.

Phase A stopped module-scoped ``emission_recalc`` children from deduping,
because two units' children recompute disjoint rows and collapsing them
dropped one unit's emissions behind a green pipeline.

Scoped children are not exempt from dedup — they dedup on their own
carbon report module instead, so two units stay disjoint while one
unit's back-to-back re-upload still collapses.

Two things have to stay true, and neither is enforced by the type
system:

1. The Python side and the SQL side must classify a config identically.
   They are written in different languages against the same idea, so a
   drift here silently re-opens the bug.
2. ``acquire_factor_recalc_lock`` may only be narrowed to include the
   unit while that scoped dedup exists. It is the only thing preventing
   duplicate ``data_entry_emissions`` rows, which have no constraint.
"""

import inspect

from app.models.data_ingestion import EMISSION_RECALC_UNSCOPED_SQL
from app.tasks import _chain
from app.tasks._chain import EMISSION_RECALC_DEDUP, _pins_module_scope
from app.tasks._locks import acquire_factor_recalc_lock

# (config, is_scoped) — the SQL side tests
# ``meta -> 'config' -> 'carbon_report_module_ids' IS NULL``, which is SQL
# NULL only when the key is absent.  A present-but-empty list and a JSON
# null are both *not* SQL NULL, so both count as scoped.  Python must say
# the same thing from key presence alone.
TRUTH_TABLE = [
    ({}, False),
    ({"other_key": 1}, False),
    (None, False),
    ({"carbon_report_module_ids": [101]}, True),
    ({"carbon_report_module_ids": []}, True),
    ({"carbon_report_module_ids": None}, True),
]


def test_pins_module_scope_truth_table():
    """Key presence, not truthiness — `[]` and `None` are still scoped.

    Truthiness here would be a silent bug: ``[]`` is falsy, so a
    truthiness test would call it unscoped while the SQL predicate calls
    it scoped, and the two sides would disagree on exactly the rows the
    partial unique index covers.
    """
    for config, expected in TRUTH_TABLE:
        assert _pins_module_scope(config) is expected, config


def test_sql_predicate_is_the_is_null_form_python_mirrors():
    """The Python check is only correct against this exact SQL shape.

    ``IS NULL`` on ``->`` is true only for an absent key. If the SQL ever
    becomes a truthiness or emptiness test, ``_pins_module_scope`` has to
    change with it — pin the pairing so that edit cannot pass unnoticed.
    """
    assert EMISSION_RECALC_UNSCOPED_SQL == (
        "meta -> 'config' -> 'carbon_report_module_ids' IS NULL"
    )
    assert EMISSION_RECALC_DEDUP.extra_predicate == EMISSION_RECALC_UNSCOPED_SQL


def test_scoped_children_keep_a_dedup_config():
    """Scoped children dedup on their own module — never not at all.

    Phase A's first cut simply dropped dedup for scoped children, which
    fixed the cross-unit drop but left one unit's back-to-back re-upload
    recomputing identical rows twice. Removing this config would restore
    that, and nothing downstream would notice: duplicate work is silent
    until it becomes duplicate rows.
    """
    scoped = _chain.EMISSION_RECALC_SCOPED_DEDUP
    assert scoped.scoped_config_key == "carbon_report_module_ids"
    assert scoped.constraint_name == "uq_emission_recalc_active_scoped"
    assert scoped.constraint_name != EMISSION_RECALC_DEDUP.constraint_name, (
        "the scoped and unscoped configs must name different indexes, or a "
        "race loss on one is misreported as the other"
    )


def test_lock_may_only_gain_unit_scope_while_scoped_children_dedup():
    """Pins the #2527 Phase B ordering, mechanically.

    ``acquire_factor_recalc_lock`` keys on ``(module_type_id, year)``
    with no unit scope, so two recalcs for the same module serialize.
    ``data_entry_emissions`` has no unique constraint, so that lock is
    the only thing standing between concurrent recalcs and duplicate
    rows.

    Narrowing the lock is safe **only** while scoped children dedup on
    their own key — which they now do. If someone removes that dedup and
    narrows the lock, the two runs can interleave and double-write,
    silently, which is the same failure class Phase A fixed. Fail here
    rather than in the data.
    """
    lock_params = set(inspect.signature(acquire_factor_recalc_lock).parameters)
    lock_is_unit_scoped = bool(lock_params & {"unit_id", "carbon_report_module_id"})
    scoped_children_dedup = hasattr(_chain, "EMISSION_RECALC_SCOPED_DEDUP")

    assert not (lock_is_unit_scoped and not scoped_children_dedup), (
        "acquire_factor_recalc_lock has gained a unit-level parameter "
        f"({sorted(lock_params)}) while module-scoped emission_recalc "
        "children no longer dedup. Two concurrent recalcs for the same "
        "carbon report module can now interleave and write duplicate "
        "data_entry_emissions rows, which no constraint prevents."
    )
