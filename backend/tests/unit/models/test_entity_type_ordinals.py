"""Regression test pinning ``EntityType`` integer values.

Enum integer values are part of the persisted ABI: every ingestion job
serialises ``entity_type.value`` into ``DataIngestionJob.meta["config"]``
and we round-trip via ``EntityType(value)`` to route to the right
provider.  Inserting a new member at the front shifts the ordinals of
the existing members, which silently mis-routes every historical row
the next time it's read back.

This test fails loudly if anyone reorders the enum without thinking
about the persisted-state implications.  New members must be appended,
not inserted in the middle.
"""

from app.models.data_ingestion import EntityType


def test_entity_type_int_values_are_stable():
    """Persisted ``meta["config"]["entity_type"]`` integers must keep
    their meaning across deploys.  If you need to add a new member,
    append it (not insert) — and update this test in lockstep so the
    ABI change is explicit in code review."""
    assert EntityType.MODULE_PER_YEAR.value == 1
    assert EntityType.MODULE_UNIT_SPECIFIC.value == 2
    assert EntityType.GLOBAL_PER_YEAR.value == 3


def test_entity_type_round_trip_by_value():
    """``EntityType(value)`` reconstructs the original member — the
    operation that runs on every persisted job read.  Combined with
    the ordinal pin above, this verifies historical rows containing
    ``1`` and ``2`` still mean MODULE_PER_YEAR / MODULE_UNIT_SPECIFIC."""
    assert EntityType(1) is EntityType.MODULE_PER_YEAR
    assert EntityType(2) is EntityType.MODULE_UNIT_SPECIFIC
    assert EntityType(3) is EntityType.GLOBAL_PER_YEAR
