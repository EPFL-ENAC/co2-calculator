"""Sort / search / pagination matrix over EVERY registered module handler.

Regression net for the class of bugs found while testing #1721:

- buildings couldn't sort by ``room_surface_square_meter`` (the value lives
  on the joined ``building_rooms`` row, not in entry data);
- purchase couldn't sort by ``currency`` (key missing from ``sort_map`` →
  "Cannot sort by unknown field");
- research facilities couldn't sort or search at all (``sort_map`` had only
  id/kg_co2eq, ``filter_map`` was empty).

Instead of hand-writing per-module cases, this drives
``DataEntryRepository.get_submodule_data`` for every det in
``MODULE_HANDLERS`` with two synthesized entries and asserts, for each det:

- every ``sort_map`` key works asc AND desc (no "unknown field", no SQL
  error) and returns both rows;
- for every data-backed sort key the ordering actually follows the
  synthesized values (A < B);
- every ``filter_map`` key finds exactly the matching row;
- pagination (limit=1, offset sweep) partitions the rows without dupes.

Entry data is synthesized FROM the maps themselves (float-typed exprs get
1.0/2.0, everything else gets "alpha-…"/"zulu-…"), so a new sort/filter key
is covered the moment it is added to a handler — and a key pointing at a
column the query never joins fails here immediately.

Requires Docker — see ``conftest.py``'s ``postgres_container`` fixture.
"""

from typing import Any

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.building_room import BuildingRoom
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.factor import Factor
from app.models.unit import Unit
from app.repositories.data_entry_repo import DataEntryRepository
from app.schemas.data_entry import MODULE_HANDLERS

_YEAR = 2025

# Values chosen so ascending order is deterministic: A < B for both the
# numeric and the string synthesis ("alpha" < "zulu").
_A_NUM, _B_NUM = 1.0, 2.0
_A_STR, _B_STR = "alpha", "zulu"

# Per-det extras for response-DTO required fields that no sort/filter map
# references (the maps drive the synthesis; DTO validation needs the rest).
_EXTRA_DATA: dict[DataEntryTypeEnum, dict[str, Any]] = {
    DataEntryTypeEnum.plane: {"user_institutional_id": "U-MATRIX"},
    DataEntryTypeEnum.train: {"user_institutional_id": "U-MATRIX"},
}

# Keys whose values must be domain-shaped rather than generic strings.
# (A, B) pairs still sort A < B.
_KEY_VALUES: dict[str, tuple[Any, Any]] = {
    "departure_date": ("2025-01-02", "2025-11-30"),
    # Sorted via a CASE over the frequency enum, not lexically.
    "requests_per_user_per_day": ("1_5", "gt_100"),
}


def _is_float_expr(expr: Any) -> bool:
    try:
        return isinstance(expr.type, (sa.Float, sa.Numeric, sa.Integer))
    except AttributeError:
        return False


def _order_checkable(expr: Any, det_has_factor: bool) -> bool:
    """True when the sort key must order by the synthesized values: it reads
    entry data (coalesce fallbacks included), or it reads the factor tables
    and this det got matched factors seeded (kind-carrying handlers)."""
    try:
        sql = str(expr.compile(compile_kwargs={"literal_binds": False}))
    except Exception:
        return False
    if "data_entries.data" in sql:
        return True
    return det_has_factor and ("factors" in sql or "building_rooms" in sql)


def _synth_data(handler: Any, det: DataEntryTypeEnum, variant: str) -> dict:
    """Build entry data from the handler's own maps: every mapped key gets a
    deterministic value; floats sort numerically, strings alphabetically."""
    is_a = variant == "A"
    data: dict[str, Any] = dict(_EXTRA_DATA.get(det, {}))
    for key, expr in {**handler.sort_map, **handler.filter_map}.items():
        if key in ("id", "kg_co2eq"):
            continue
        if key in _KEY_VALUES:
            data[key] = _KEY_VALUES[key][0] if is_a else _KEY_VALUES[key][1]
        elif _is_float_expr(expr):
            data[key] = _A_NUM if is_a else _B_NUM
        else:
            data[key] = f"{_A_STR}-{key}" if is_a else f"{_B_STR}-{key}"
    return data


async def _seed_det(
    session: AsyncSession, module_id: int, det: DataEntryTypeEnum, handler: Any
) -> tuple[int, int]:
    """Two entries per det: A sorts before B on every synthesized key."""
    entry_a = DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=det.value,
        data=_synth_data(handler, det, "A"),
        year=_YEAR,
    )
    entry_b = DataEntry(
        carbon_report_module_id=module_id,
        data_entry_type_id=det.value,
        data=_synth_data(handler, det, "B"),
        year=_YEAR,
    )
    session.add_all([entry_a, entry_b])
    # Kind-carrying handlers also get a matched factor per entry, mirroring
    # the synthesized data into classification AND values — so factor-backed
    # sort/filter keys are genuinely order-checkable (matrix blind spot found
    # in review: Factor-only keys used to pass NULL-ordered).
    if handler.kind_field is not None:
        for entry in (entry_a, entry_b):
            session.add(
                Factor(
                    emission_type_id=1,
                    data_entry_type_id=det.value,
                    classification=dict(entry.data),
                    values=dict(entry.data),
                    year=_YEAR,
                )
            )
    await session.commit()
    if entry_a.id is None or entry_b.id is None:
        raise ValueError("seeded entries must have ids")
    return entry_a.id, entry_b.id


async def _fetch(
    repo: DataEntryRepository,
    module_id: int,
    det: DataEntryTypeEnum,
    **kwargs: Any,
):
    params: dict[str, Any] = {
        "carbon_report_module_id": module_id,
        "data_entry_type_id": det.value,
        "limit": 10,
        "offset": 0,
        "sort_by": "id",
        "sort_order": "asc",
    }
    params.update(kwargs)
    return await repo.get_submodule_data(**params)


@pytest.mark.asyncio
async def test_sort_search_pagination_matrix_all_modules(pg_dsn):
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    failures: list[str] = []
    try:
        async with Sf() as s:
            unit = Unit(
                institutional_code="TEST-MATRIX",
                institutional_id="TEST-UNIT-MATRIX",
                name="Matrix Unit",
                level=1,
            )
            s.add(unit)
            await s.commit()
            report = CarbonReport(year=_YEAR, unit_id=unit.id)
            s.add(report)
            await s.commit()
            assert report.id is not None

            modules: dict[int, int] = {}  # module_type_id → module id
            repo = DataEntryRepository(s)

            for det, handler in sorted(
                MODULE_HANDLERS.items(), key=lambda kv: kv[0].value
            ):
                mt = handler.module_type.value
                if mt not in modules:
                    module = CarbonReportModule(
                        carbon_report_id=report.id, module_type_id=mt
                    )
                    s.add(module)
                    await s.commit()
                    if module.id is None:
                        raise ValueError("module must have an id")
                    modules[mt] = module.id
                module_id = modules[mt]

                id_a, id_b = await _seed_det(s, module_id, det, handler)

                # ── every sort key, both directions ─────────────────────
                for key, expr in handler.sort_map.items():
                    for order in ("asc", "desc"):
                        try:
                            resp = await _fetch(
                                repo,
                                module_id,
                                det,
                                sort_by=key,
                                sort_order=order,
                            )
                        except Exception as exc:  # noqa: BLE001 — matrix report
                            failures.append(f"{det.name}: sort {key} {order}: {exc!r}")
                            continue
                        if len(resp.items) != 2:
                            failures.append(
                                f"{det.name}: sort {key} {order}: expected 2 rows, "
                                f"got {len(resp.items)}"
                            )
                            continue
                        if key != "kg_co2eq" and _order_checkable(
                            expr, handler.kind_field is not None
                        ):
                            got = [item.id for item in resp.items]
                            want = [id_a, id_b] if order == "asc" else [id_b, id_a]
                            if got != want:
                                failures.append(
                                    f"{det.name}: sort {key} {order}: "
                                    f"order {got}, expected {want}"
                                )

                # ── every filter key finds exactly the matching row ─────
                for key in handler.filter_map:
                    needle = f"{_A_STR}-{key}"
                    try:
                        resp = await _fetch(repo, module_id, det, filter=needle)
                    except Exception as exc:  # noqa: BLE001 — matrix report
                        failures.append(f"{det.name}: search {key}: {exc!r}")
                        continue
                    got_ids = {item.id for item in resp.items}
                    if got_ids != {id_a} or resp.summary.total_items != 1:
                        failures.append(
                            f"{det.name}: search {key}={needle!r}: ids={got_ids} "
                            f"total={resp.summary.total_items}, expected only entry A"
                        )

                # ── pagination partitions without dupes ─────────────────
                try:
                    page1 = await _fetch(repo, module_id, det, limit=1, offset=0)
                    page2 = await _fetch(repo, module_id, det, limit=1, offset=1)
                except Exception as exc:  # noqa: BLE001 — matrix report
                    failures.append(f"{det.name}: pagination: {exc!r}")
                else:
                    ids = [i.id for i in page1.items] + [i.id for i in page2.items]
                    totals = (page1.summary.total_items, page2.summary.total_items)
                    if sorted(ids) != sorted([id_a, id_b]) or totals != (2, 2):
                        failures.append(
                            f"{det.name}: pagination: pages={ids} totals={totals}"
                        )
    finally:
        await engine.dispose()

    assert not failures, "matrix failures:\n" + "\n".join(failures)


@pytest.mark.asyncio
async def test_buildings_sort_by_surface_from_building_rooms(pg_dsn):
    """#1721 report 1: surface lives on the joined ``building_rooms`` row —
    sorting must follow it even though entry data carries no surface."""
    engine = create_async_engine(pg_dsn, future=True)
    Sf = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with Sf() as s:
            unit = Unit(
                institutional_code="TEST-SURF",
                institutional_id="TEST-UNIT-SURF",
                name="Surface Unit",
                level=1,
            )
            s.add(unit)
            await s.commit()
            report = CarbonReport(year=_YEAR, unit_id=unit.id)
            s.add(report)
            await s.commit()
            module = CarbonReportModule(
                carbon_report_id=report.id,
                module_type_id=MODULE_HANDLERS[
                    DataEntryTypeEnum.building
                ].module_type.value,
            )
            s.add(module)
            await s.commit()
            assert module.id is not None

            s.add_all(
                [
                    BuildingRoom(
                        room_name="R-SMALL",
                        building_location="LOC",
                        building_name="GC",
                        room_type="office",
                        room_surface_square_meter=10.0,
                    ),
                    BuildingRoom(
                        room_name="R-BIG",
                        building_location="LOC",
                        building_name="GC",
                        room_type="office",
                        room_surface_square_meter=99.0,
                    ),
                ]
            )
            small = DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.building.value,
                data={
                    "building_name": "GC",
                    "room_name": "R-SMALL",
                    "room_type": "office",
                },
                year=_YEAR,
            )
            big = DataEntry(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.building.value,
                data={
                    "building_name": "GC",
                    "room_name": "R-BIG",
                    "room_type": "office",
                },
                year=_YEAR,
            )
            s.add_all([small, big])
            await s.commit()

            repo = DataEntryRepository(s)
            resp = await repo.get_submodule_data(
                carbon_report_module_id=module.id,
                data_entry_type_id=DataEntryTypeEnum.building.value,
                limit=10,
                offset=0,
                sort_by="room_surface_square_meter",
                sort_order="desc",
            )
    finally:
        await engine.dispose()

    names = [item.room_name for item in resp.items]
    assert names == ["R-BIG", "R-SMALL"], (
        f"desc surface sort must order by the building_rooms value; got {names}"
    )
