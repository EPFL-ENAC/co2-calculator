"""#2715: the embodied-energy breakdown must not drop rows on a missing surface.

``get_embodied_energy_by_category`` apportions each row's ``kg_co2eq`` across
factor categories. It used to read ``meta['room_surface_square_meter']`` first
and ``continue`` past any row that lacked it — silently, so the breakdown
under-reported and looked complete.

The surface never affected the result. The apportionment is a ratio and the
surface was a common multiplier on both sides of it:

    result[cat] = (surface * ef[cat]) * kg / (surface * SUM(ef))
                = ef[cat] * kg / SUM(ef)

So the guard excluded rows on the basis of a number that cancels. It mattered
because the value is a *snapshot* spilled into ``meta`` by ``**ctx``, not a
field anything guarantees: any write path that does not happen to record it
made its rows vanish from the breakdown.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.data_entry_emission_repo import DataEntryEmissionRepository


def _row(kg, meta):
    r = MagicMock()
    r.kg_co2eq = kg
    r.meta = meta
    return r


def _factor(fid, category, ef):
    f = MagicMock()
    f.id = fid
    f.category = category
    f.ef = ef
    return f


def _repo(rows, factors):
    """A repo whose two queries return ``rows`` then ``factors``."""
    session = MagicMock()
    rows_result, factors_result = MagicMock(), MagicMock()
    rows_result.all.return_value = rows
    factors_result.all.return_value = factors
    session.execute = AsyncMock(side_effect=[rows_result, factors_result])
    return DataEntryEmissionRepository(session)


FACTORS = [_factor(1, "concrete", 3.0), _factor(2, "steel", 1.0)]
USED = {"factors_used": [{"id": 1}, {"id": 2}]}


@pytest.mark.asyncio
async def test_row_without_room_surface_is_still_counted():
    """The regression: no surface in meta must not mean no contribution.

    Before #2715 this returned ``[]`` — the row was skipped and its 800 kg
    silently left the breakdown.
    """
    repo = _repo([_row(800.0, dict(USED))], FACTORS)

    result = dict(await repo.get_embodied_energy_by_category(carbon_report_id=1))

    assert result == pytest.approx({"concrete": 600.0, "steel": 200.0})


@pytest.mark.asyncio
async def test_surface_does_not_change_the_apportionment():
    """Pins why the guard was safe to delete: the surface cancels.

    Same row, four surfaces spanning six orders of magnitude, plus none at
    all — one identical breakdown. If a future change makes the surface
    load-bearing again, this fails rather than silently re-weighting a
    published number.
    """
    outputs = []
    for surface in (None, 0.001, 1.0, 42.0, 1000.0):
        meta = dict(USED)
        if surface is not None:
            meta["room_surface_square_meter"] = surface
        repo = _repo([_row(900.0, meta)], FACTORS)
        outputs.append(
            dict(await repo.get_embodied_energy_by_category(carbon_report_id=1))
        )

    for got in outputs[1:]:
        assert got == pytest.approx(outputs[0])
    assert outputs[0] == pytest.approx({"concrete": 675.0, "steel": 225.0})


@pytest.mark.asyncio
async def test_row_without_usable_factors_still_lands_in_unknown():
    """Unchanged behaviour: no factor ids means the total is not lost.

    This bucket is why the missing-surface skip was a bug rather than a
    deliberate exclusion — the function already had a way to keep a row it
    could not apportion.
    """
    repo = _repo([_row(500.0, {"factors_used": []})], FACTORS)

    result = dict(await repo.get_embodied_energy_by_category(carbon_report_id=1))

    assert result == pytest.approx({"unknown": 500.0})


@pytest.mark.asyncio
async def test_mixed_rows_with_and_without_surface_both_contribute():
    """The real shape of the bug: a report holding both kinds of row.

    One row carries the snapshot, one does not. Before the fix the breakdown
    reported only the first and looked entirely plausible.
    """
    rows = [
        _row(800.0, {**USED, "room_surface_square_meter": 42.0}),
        _row(400.0, dict(USED)),
    ]
    repo = _repo(rows, FACTORS)

    result = dict(await repo.get_embodied_energy_by_category(carbon_report_id=1))

    # 1200 kg total, split 3:1 by the two factors' EFs.
    assert result == pytest.approx({"concrete": 900.0, "steel": 300.0})
