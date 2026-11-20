"""Unit tests for DataEntryEmissionService."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.data_entry import DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmissionRow,
    EmissionComputation,
    FactorQuery,
)
from app.models.factor import Factor
from app.modules.emissions import EmissionType
from app.modules.emissions.registry import (
    DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION,
    ROLLUP_EMISSION_TYPE_IDS,
)
from app.modules_planner.headcount import (
    PlannerHeadCountCreate,
    PlannerHeadcountModuleHandler,
)
from app.schemas.data_entry import DataEntryResponse
from app.services.data_entry_emission_service import DataEntryEmissionService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service() -> DataEntryEmissionService:
    session = MagicMock()
    session.flush = AsyncMock()
    service = DataEntryEmissionService(session)
    service.repo = MagicMock()
    service.repo.delete_by_data_entry_id = AsyncMock()
    service.repo.bulk_create = AsyncMock()
    return service


def _make_data_entry_response(data: dict) -> DataEntryResponse:
    return DataEntryResponse(
        id=1,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
        carbon_report_module_id=10,
        data=data,
    )


def _make_fake_emission() -> DataEntryEmissionRow:
    """A ``prepare_create``-shaped stand-in — real dataclass, not a mock,
    since ``upsert_by_data_entry`` calls ``.to_orm()`` on what it returns.
    """
    return DataEntryEmissionRow(
        data_entry_id=1,
        emission_type_id=1,
        kg_co2eq=123.45,
        # Stamped, as prepare_create returns them (#2527).
        carbon_report_module_id=10,
        data_entry_type_id=DataEntryTypeEnum.plane.value,
    )


# ---------------------------------------------------------------------------
# upsert_by_data_entry — passes data through to prepare_create unchanged
# ---------------------------------------------------------------------------
#
# Note: the historical "strip kg_co2eq before recompute" workaround in
# upsert_by_data_entry was removed once the CSV/API ingestion paths stopped
# persisting kg_co2eq into DataEntry.data. The override is now carried
# transiently via prepare_create(kg_co2eq_override=...).


@pytest.mark.asyncio
async def test_upsert_passes_data_through_unchanged():
    """upsert_by_data_entry must forward the response to prepare_create
    without mutating its data dict (no stale-kg_co2eq workaround anymore).
    """
    service = _make_service()
    fake_emission = _make_fake_emission()
    service.repo.bulk_create = AsyncMock(return_value=[fake_emission])

    data_entry = _make_data_entry_response(
        {"number_of_trips": 3, "distance_one_trip_km": 500.0}
    )

    captured: list[DataEntryResponse] = []

    async def fake_prepare_create(
        de: DataEntryResponse,
        kg_co2eq_override: float | None = None,
    ) -> list[DataEntryEmissionRow]:
        captured.append(de)
        return [fake_emission]

    with patch.object(service, "prepare_create", side_effect=fake_prepare_create):
        await service.upsert_by_data_entry(data_entry)

    called_with = captured[0]
    assert called_with.data == {"number_of_trips": 3, "distance_one_trip_km": 500.0}


@pytest.mark.asyncio
async def test_upsert_deletes_then_creates_emissions():
    """Existing emissions must be deleted before new ones are inserted."""
    service = _make_service()
    fake_emission = _make_fake_emission()
    service.repo.bulk_create = AsyncMock(return_value=[fake_emission])

    call_order: list[str] = []
    service.repo.delete_by_data_entry_id = AsyncMock(
        side_effect=lambda *_: call_order.append("delete")
    )
    service.repo.bulk_create = AsyncMock(
        side_effect=lambda *_: call_order.append("create") or [fake_emission]
    )

    data_entry = _make_data_entry_response({"number_of_trips": 1})

    async def fake_prepare_create(de: DataEntryResponse) -> list[DataEntryEmissionRow]:
        return [fake_emission]

    with patch.object(service, "prepare_create", side_effect=fake_prepare_create):
        await service.upsert_by_data_entry(data_entry)

    assert call_order == ["delete", "create"]


@pytest.mark.asyncio
async def test_upsert_returns_none_and_flushes_when_no_emissions():
    """When prepare_create yields nothing, existing emissions are cleared
    and None returned.
    """
    service = _make_service()

    data_entry = _make_data_entry_response({"number_of_trips": 1})

    async def fake_prepare_create(de: DataEntryResponse) -> list[DataEntryEmissionRow]:
        return []

    with patch.object(service, "prepare_create", side_effect=fake_prepare_create):
        result = await service.upsert_by_data_entry(data_entry)

    assert result is None
    service.repo.delete_by_data_entry_id.assert_awaited_once_with(data_entry.id)
    service.session.flush.assert_awaited_once()
    service.repo.bulk_create.assert_not_awaited()


# ---------------------------------------------------------------------------
# prepare_create — kg_co2eq_override (CSV / API ingestion path)
# ---------------------------------------------------------------------------
#
# The override short-circuits the formula: we produce a single emission per
# computation with the given kg_co2eq and primary_factor_id=None, and the
# value is NEVER read from data_entry.data.kg_co2eq.


@pytest.mark.asyncio
async def test_prepare_create_with_kg_co2eq_override_short_circuits_formula():
    """When kg_co2eq_override is set, the formula path is bypassed and a
    single emission with the override value (and primary_factor_id=None) is
    returned — even when the data dict has no kg_co2eq key.
    """
    service = _make_service()

    factor = MagicMock(spec=Factor)
    factor.id = 99
    factor.emission_type_id = EmissionType.commuting__cycling.value
    factor.values = {"ef_kg_co2eq_per_unit": 0.5, "unit": "km"}

    de = _make_data_entry_response({"number_of_trips": 2})  # no kg_co2eq key

    with (
        patch.object(service, "_fetch_factors", new=AsyncMock(return_value=[factor])),
        patch.object(
            service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
        ),
        patch(
            "app.services.data_entry_emission_service.resolve_emission_types",
            return_value=[EmissionType.professional_travel__plane],
        ),
        patch(
            "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
        ) as mock_handler_cls,
    ):
        mock_handler = MagicMock()
        mock_handler.kind_field = None
        mock_handler.pre_compute = AsyncMock(return_value={})
        mock_handler.resolve_computations = MagicMock(
            return_value=[
                EmissionComputation(
                    emission_type=EmissionType.professional_travel__plane,
                    factor_id=99,
                )
            ]
        )
        mock_handler_cls.return_value = mock_handler

        results = await service.prepare_create(de, kg_co2eq_override=42.0)

    assert len(results) == 1
    assert results[0].kg_co2eq == 42.0
    assert results[0].primary_factor_id is None


@pytest.mark.asyncio
async def test_prepare_create_does_not_read_kg_co2eq_from_data():
    """A kg_co2eq value sitting in data_entry.data must NOT be picked up as
    an override — the channel is exclusively the kg_co2eq_override param.
    """
    service = _make_service()

    factor = MagicMock(spec=Factor)
    factor.id = 99
    factor.emission_type_id = EmissionType.professional_travel__plane.value
    factor.values = {"ef_kg_co2eq_per_km": 0.2}

    # data has a stray kg_co2eq from a hypothetical legacy row — must be ignored
    de = _make_data_entry_response({"distance_km": 100.0, "kg_co2eq": 99999.0})

    with (
        patch.object(service, "_fetch_factors", new=AsyncMock(return_value=[factor])),
        patch.object(
            service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
        ),
        patch(
            "app.services.data_entry_emission_service.resolve_emission_types",
            return_value=[EmissionType.professional_travel__plane],
        ),
        patch(
            "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
        ) as mock_handler_cls,
    ):
        mock_handler = MagicMock()
        mock_handler.kind_field = None
        mock_handler.pre_compute = AsyncMock(return_value={})
        mock_handler.resolve_computations = MagicMock(
            return_value=[
                EmissionComputation(
                    emission_type=EmissionType.professional_travel__plane,
                    factor_id=99,
                    formula_key="ef_kg_co2eq_per_km",
                    quantity_key="distance_km",
                )
            ]
        )
        mock_handler_cls.return_value = mock_handler

        # No override → formula path runs; the stray kg_co2eq=99999 must be ignored.
        results = await service.prepare_create(de)

    assert len(results) == 1
    # Result is from the formula: 100.0 km * 0.2 = 20.0
    assert results[0].kg_co2eq == pytest.approx(20.0)
    assert results[0].primary_factor_id == 99


@pytest.mark.asyncio
async def test_prepare_create_equipment_without_factor_yields_no_row_not_zero():
    """Imported inventory without a sub_class resolves no factor: the entry
    gets no emission row (kg_co2eq null, skipped by totals), never a 0.
    """
    service = _make_service()
    resolver = MagicMock()
    resolver.resolve = AsyncMock(return_value=None)
    de = DataEntryResponse(
        id=7,
        data_entry_type_id=DataEntryTypeEnum.scientific.value,
        carbon_report_module_id=10,
        data={"equipment_id": "INV-1", "equipment_class": "Optical microscopes"},
    )

    with patch.object(
        service, "_get_year_from_data_entry", new=AsyncMock(return_value=2025)
    ):
        results = await service.prepare_create(de, factor_resolver=resolver)

    assert results == []


# ---------------------------------------------------------------------------
# #2527 — the denormalized join keys are stamped on every produced row
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prepare_create_stamps_module_and_type_on_every_row():
    """Leaves *and* the rollup row carry the parent entry's join keys.

    They are NOT NULL on ``data_entry_emissions`` and the submodule
    aggregate now filters on them, so a row that missed the stamp would
    vanish from every total instead of failing loudly.
    """
    service = _make_service()

    factor = MagicMock(spec=Factor)
    factor.id = 7
    factor.emission_type_id = None
    factor.values = {"kg_co2eq_per_fte": 100.0}

    de = DataEntryResponse(
        id=55,
        data_entry_type_id=DataEntryTypeEnum.member.value,
        carbon_report_module_id=4242,
        data={"fte": 1.0},
    )

    with (
        patch.object(service, "_fetch_factors", new=AsyncMock(return_value=[factor])),
        patch.object(
            service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
        ),
        patch(
            "app.services.data_entry_emission_service.resolve_emission_types",
            return_value=[EmissionType.food, EmissionType.waste],
        ),
        patch(
            "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
        ) as mock_handler_cls,
    ):
        mock_handler = MagicMock()
        mock_handler.kind_field = None
        mock_handler.pre_compute = AsyncMock(return_value={"fte": 1.0})
        mock_handler.resolve_computations = MagicMock(
            side_effect=lambda _de, emission_type, _ctx: [
                EmissionComputation(
                    emission_type=emission_type,
                    factor_id=factor.id,
                    formula_key="kg_co2eq_per_fte",
                    quantity_key="fte",
                )
            ]
        )
        mock_handler_cls.return_value = mock_handler

        results = await service.prepare_create(de)

    # two leaves + the headcount rollup row
    assert len(results) == 3
    assert {r.emission_type_id for r in results} & ROLLUP_EMISSION_TYPE_IDS
    assert all(r.carbon_report_module_id == 4242 for r in results)
    assert all(r.data_entry_type_id == DataEntryTypeEnum.member.value for r in results)


def test_to_orm_raises_on_unstamped_row():
    """The single guard covering create / bulk_create / upsert / the
    non-psycopg bulk_copy fallback — no silent default into module 0.
    """
    row = DataEntryEmissionRow(data_entry_id=9, emission_type_id=1, kg_co2eq=1.0)

    with pytest.raises(ValueError, match="was not stamped"):
        row.to_orm()


# ---------------------------------------------------------------------------
# meta_extras — distance_km / weight_kg stored for headcount categories
# ---------------------------------------------------------------------------


class TestMetaExtras:
    """Tests that headcount commuting/food/waste emissions carry named quantity keys."""

    def _make_service(self) -> DataEntryEmissionService:
        session = MagicMock()
        session.flush = AsyncMock()
        return DataEntryEmissionService(session)

    def _make_factor(self, emission_type_value: int, factor_values: dict):

        f = MagicMock(spec=Factor)
        f.id = 99
        f.emission_type_id = emission_type_value
        f.values = factor_values
        return f

    @pytest.mark.asyncio
    async def test_commuting_emission_has_distance_km(self):
        from app.models.data_entry import DataEntryTypeEnum
        from app.modules.emissions import EmissionType
        from app.schemas.data_entry import DataEntryResponse

        service = self._make_service()
        # fte=1.0, number_of_unit_per_fte=4000 → quantity = 4000 km
        factor = self._make_factor(
            EmissionType.commuting__cycling.value,
            {
                "ef_kg_co2eq_per_unit": 0.0,
                "number_of_unit_per_fte": 4000.0,
                "unit": "km",
            },
        )
        de = DataEntryResponse(
            id=1,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=10,
            data={"fte": 1.0},
        )

        with (
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[factor])
            ),
            # #2050 J4: prepare_create primes the Strategy-B memo in one query
            # before the computation loop, which is its own DB seam.
            patch.object(
                service,
                "_prime_factor_query_cache",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(
                service,
                "_get_report_for_data_entry",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[EmissionType.commuting],
            ),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
            ) as mock_handler_cls,
        ):
            from app.modules.headcount import HeadcountMemberModuleHandler

            mock_handler = HeadcountMemberModuleHandler()
            mock_handler.pre_compute = AsyncMock(return_value={})
            mock_handler_cls.return_value = mock_handler

            results = await service.prepare_create(de)

        assert len(results) == 1
        assert results[0].additional_value == pytest.approx(4000.0)
        assert "distance_km" not in results[0].meta
        assert "weight_kg" not in results[0].meta

    @pytest.mark.asyncio
    async def test_food_emission_has_weight_kg(self):
        from app.models.data_entry import DataEntryTypeEnum
        from app.modules.emissions import EmissionType
        from app.schemas.data_entry import DataEntryResponse

        service = self._make_service()
        factor = self._make_factor(
            EmissionType.food__vegetarian.value,
            {
                "ef_kg_co2eq_per_unit": 0.0,
                "number_of_unit_per_fte": 160.0,
                "unit": "kg",
            },
        )
        de = DataEntryResponse(
            id=2,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=10,
            data={"fte": 1.0},
        )

        with (
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[factor])
            ),
            # #2050 J4: prepare_create primes the Strategy-B memo in one query
            # before the computation loop, which is its own DB seam.
            patch.object(
                service,
                "_prime_factor_query_cache",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(
                service,
                "_get_report_for_data_entry",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[EmissionType.food],
            ),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
            ) as mock_handler_cls,
        ):
            from app.modules.headcount import HeadcountMemberModuleHandler

            mock_handler = HeadcountMemberModuleHandler()
            mock_handler.pre_compute = AsyncMock(return_value={})
            mock_handler_cls.return_value = mock_handler

            results = await service.prepare_create(de)

        assert len(results) == 1
        assert results[0].additional_value == pytest.approx(160.0)
        assert "weight_kg" not in results[0].meta
        assert "distance_km" not in results[0].meta

    @pytest.mark.asyncio
    async def test_non_headcount_emission_has_no_named_quantity_key(self):
        """Professional travel (plane) should not duplicate quantity keys into meta."""
        from app.models.data_entry import DataEntryTypeEnum
        from app.modules.emissions import EmissionType
        from app.schemas.data_entry import DataEntryResponse

        service = self._make_service()
        factor = self._make_factor(
            EmissionType.professional_travel__plane__eco.value,
            {
                "ef_kg_co2eq_per_unit": 0.5,
                "unit": "km",
            },
        )
        de = DataEntryResponse(
            id=3,
            data_entry_type_id=DataEntryTypeEnum.plane.value,
            carbon_report_module_id=10,
            data={"distance_km": 1000.0},
        )

        with (
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[factor])
            ),
            # #2050 J4: prepare_create primes the Strategy-B memo in one query
            # before the computation loop, which is its own DB seam.
            patch.object(
                service,
                "_prime_factor_query_cache",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(
                service,
                "_get_report_for_data_entry",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[EmissionType.professional_travel__plane__eco],
            ),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
            ) as mock_handler_cls,
        ):
            mock_handler = MagicMock()
            mock_handler.kind_field = None
            mock_handler.pre_compute = AsyncMock(return_value={})
            mock_handler.resolve_computations.return_value = [
                __import__(
                    "app.models.data_entry_emission",
                    fromlist=["EmissionComputation"],
                ).EmissionComputation(
                    emission_type=EmissionType.professional_travel__plane__eco,
                    quantity_key="distance_km",
                    formula_key="ef_kg_co2eq_per_unit",
                )
            ]
            mock_handler_cls.return_value = mock_handler

            results = await service.prepare_create(de)

        assert len(results) == 1
        meta = results[0].meta
        # Travel inputs may include distance_km in ctx (thus present in meta),
        # but the emission row persists it in additional_value (source of truth).
        assert meta.get("distance_km") == pytest.approx(1000.0)
        assert "weight_kg" not in meta
        assert results[0].additional_value == pytest.approx(1000.0)


# ---------------------------------------------------------------------------
# _apply_formula (pure computation)
# ---------------------------------------------------------------------------


class TestApplyFormula:
    """Tests for the _apply_formula method (pure, no DB)."""

    def _make_service(self) -> DataEntryEmissionService:
        return DataEntryEmissionService(MagicMock())

    def test_key_based_simple(self):
        from app.models.data_entry_emission import EmissionComputation
        from app.modules.emissions import EmissionType

        service = self._make_service()
        comp = EmissionComputation(
            emission_type=EmissionType.food,
            quantity_key="fte",
            formula_key="kg_co2eq_per_fte",
        )
        ctx = {"fte": 0.8}
        factor_values = {"kg_co2eq_per_fte": 420.0}
        result = service._apply_formula(ctx, factor_values, comp)
        assert result == pytest.approx(336.0)

    def test_key_based_with_multiplier(self):
        from app.models.data_entry_emission import EmissionComputation
        from app.modules.emissions import EmissionType

        service = self._make_service()
        comp = EmissionComputation(
            emission_type=EmissionType.professional_travel__plane__eco,
            quantity_key="distance_km",
            formula_key="kg_co2eq_per_km",
            multiplier_key="rfi_adjustment",
            multiplier_default=1.0,
        )
        ctx = {"distance_km": 1000.0}
        factor_values = {"kg_co2eq_per_km": 0.15, "rfi_adjustment": 2.0}
        result = service._apply_formula(ctx, factor_values, comp)
        assert result == pytest.approx(300.0)

    def test_multiplier_key_missing_uses_default(self):
        from app.models.data_entry_emission import EmissionComputation
        from app.modules.emissions import EmissionType

        service = self._make_service()
        comp = EmissionComputation(
            emission_type=EmissionType.food,
            quantity_key="fte",
            formula_key="kg_co2eq_per_fte",
            multiplier_key="missing_key",
            multiplier_default=2.0,
        )
        ctx = {"fte": 1.0}
        factor_values = {"kg_co2eq_per_fte": 100.0}
        result = service._apply_formula(ctx, factor_values, comp)
        assert result == pytest.approx(200.0)

    def test_missing_quantity_raises_naming_the_entry_field(self):
        """#2050 Track J: returned None, and the caller dropped the leaf."""
        from app.models.data_entry_emission import EmissionComputation
        from app.modules.emissions import EmissionType

        service = self._make_service()
        comp = EmissionComputation(
            emission_type=EmissionType.food,
            quantity_key="fte",
            formula_key="kg_co2eq_per_fte",
        )
        ctx = {}  # missing fte
        factor_values = {"kg_co2eq_per_fte": 420.0}
        # Names the side it is missing from — entry vs factor is the first
        # thing whoever reads error_details needs to know.
        with pytest.raises(ValueError, match=r"entry\.fte"):
            service._apply_formula(ctx, factor_values, comp)

    def test_missing_formula_key_raises_naming_the_factor_field(self):
        """#2050 Track J: returned None, and the caller dropped the leaf."""
        from app.models.data_entry_emission import EmissionComputation
        from app.modules.emissions import EmissionType

        service = self._make_service()
        comp = EmissionComputation(
            emission_type=EmissionType.food,
            quantity_key="fte",
            formula_key="missing_factor_key",
        )
        ctx = {"fte": 1.0}
        factor_values = {}
        with pytest.raises(ValueError, match=r"factor\.missing_factor_key"):
            service._apply_formula(ctx, factor_values, comp)

    def test_no_keys_raises_as_a_misconfiguration(self):
        """#2050 Track J: a computation with neither a formula_func nor the
        key pair cannot be computed at all — that is a configuration bug,
        not a data gap, and it used to return None like any other.
        """
        from app.models.data_entry_emission import EmissionComputation
        from app.modules.emissions import EmissionType

        service = self._make_service()
        comp = EmissionComputation(
            emission_type=EmissionType.food,
            # no quantity_key or formula_key
        )
        with pytest.raises(ValueError, match="neither a formula_func"):
            service._apply_formula({}, {}, comp)

    def test_formula_func_takes_precedence(self):
        from app.models.data_entry_emission import EmissionComputation
        from app.modules.emissions import EmissionType

        service = self._make_service()

        def custom_formula(ctx, factor_values):
            return ctx.get("x", 0) * factor_values.get("y", 0)

        comp = EmissionComputation(
            emission_type=EmissionType.food,
            quantity_key="fte",
            formula_key="kg_co2eq_per_fte",
            formula_func=custom_formula,
        )
        ctx = {"x": 3.0, "fte": 999}
        factor_values = {"y": 5.0, "kg_co2eq_per_fte": 999}
        result = service._apply_formula(ctx, factor_values, comp)
        assert result == pytest.approx(15.0)

    def test_formula_func_returning_none_raises_with_the_null_inputs(self):
        """#2050 Track J: the common real case (an unmatched reference-data
        lookup) lands here, and the old call-site diagnostic printed two
        empty lists for it because it only knew about key-based configs.
        The reason has to come from here, where the branch is known.
        """
        from app.models.data_entry_emission import EmissionComputation
        from app.modules.emissions import EmissionType

        service = self._make_service()
        comp = EmissionComputation(
            emission_type=EmissionType.food,
            formula_func=lambda ctx, fv: None,
        )
        with pytest.raises(ValueError, match="room_surface_square_meter"):
            service._apply_formula({"room_surface_square_meter": None}, {}, comp)


# ---------------------------------------------------------------------------
# prepare_create edge cases
# ---------------------------------------------------------------------------


class TestPrepareCreate:
    # #2050 Track J: the former ``test_none_data_entry`` and
    # ``test_no_data_entry_type`` cases are gone with the guards they
    # pinned. Both described states the types make impossible —
    # ``prepare_create`` takes ``DataEntry | DataEntryResponse`` (not
    # optional), and ``data_entry_type`` is a property over a non-nullable
    # ``int`` column, so it cannot return None. Only a MagicMock could
    # reach them. An unflushed id is genuinely reachable and now raises.

    async def test_no_id_raises(self):
        service = _make_service()
        de = _make_data_entry_response({"fte": 1.0})
        de = de.model_copy(update={"id": None})
        # resolve_emission_types needs a valid type, mock it
        with (
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[MagicMock()],
            ),
            pytest.raises(ValueError, match="must be flushed"),
        ):
            await service.prepare_create(de)


# ---------------------------------------------------------------------------
# _get_year_from_data_entry
# ---------------------------------------------------------------------------


class TestGetYearFromDataEntry:
    async def test_missing_carbon_report_module_id(self):
        service = _make_service()
        de = MagicMock()
        de.carbon_report_module_id = None
        result = await service._get_year_from_data_entry(de)
        assert result is None

    async def test_module_not_found(self):
        service = _make_service()
        service.session.exec = AsyncMock(
            return_value=MagicMock(one_or_none=MagicMock(return_value=None))
        )
        de = MagicMock()
        de.carbon_report_module_id = 999
        result = await service._get_year_from_data_entry(de)
        assert result is None


# ---------------------------------------------------------------------------
# Delegation methods
# ---------------------------------------------------------------------------


class TestDelegationMethods:
    async def test_create_with_no_emissions(self):
        service = _make_service()
        de = _make_data_entry_response({"fte": 1.0})
        with patch.object(service, "prepare_create", new=AsyncMock(return_value=[])):
            result = await service.create(de)
        assert result == []

    async def test_bulk_create_delegates(self):
        service = _make_service()
        fake = [MagicMock()]
        service.repo.bulk_create = AsyncMock(return_value=fake)
        result = await service.bulk_create(fake)
        assert result == fake


# ---------------------------------------------------------------------------
# prepare_create — rollup row creation
# ---------------------------------------------------------------------------


class TestPrepareCreateRollup:
    """Verify that prepare_create appends a single rollup row for building entries."""

    @pytest.mark.asyncio
    async def test_building_gets_rollup_row(self):
        service = _make_service()

        data_entry = DataEntryResponse(
            id=99,
            data_entry_type_id=DataEntryTypeEnum.building.value,
            carbon_report_module_id=10,
            data={"room_type": "laboratories", "name": "Lab"},
        )

        leaf_types = [
            EmissionType.buildings__rooms__lighting,
            EmissionType.buildings__rooms__cooling,
        ]
        fake_factor = MagicMock()
        fake_factor.id = 7
        fake_factor.emission_type_id = EmissionType.buildings__rooms__lighting.value
        fake_factor.values = {}

        fake_comp = EmissionComputation(
            emission_type=EmissionType.buildings__rooms__lighting,
            formula_key="",
            quantity_key="",
        )

        with (
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=leaf_types,
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[fake_factor])
            ),
            patch.object(service, "_apply_formula", return_value=500.0),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type"
            ) as mock_handler_cls,
        ):
            mock_handler = MagicMock()
            mock_handler.kind_field = None
            mock_handler.pre_compute = AsyncMock(return_value={})
            mock_handler.resolve_computations = MagicMock(return_value=[fake_comp])
            mock_handler_cls.return_value = mock_handler

            results = await service.prepare_create(data_entry)

        rollup_et = DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION[DataEntryTypeEnum.building]
        rollup_rows = [r for r in results if r.emission_type_id == rollup_et.value]
        leaf_rows = [r for r in results if r.emission_type_id != rollup_et.value]

        # Must have exactly one rollup row
        assert len(rollup_rows) == 1, f"Expected 1 rollup row, got {len(rollup_rows)}"
        rollup = rollup_rows[0]

        # Rollup row properties
        assert rollup.primary_factor_id == 7
        assert rollup.meta.get("is_rollup") is True
        assert rollup.kg_co2eq == pytest.approx(sum(r.kg_co2eq for r in leaf_rows)), (
            "Rollup kg_co2eq must equal the sum of all leaf rows"
        )

    @pytest.mark.asyncio
    async def test_non_building_gets_no_rollup_row(self):
        """Entry types without a rollup mapping must not get a rollup row."""
        service = _make_service()

        data_entry = DataEntryResponse(
            id=100,
            data_entry_type_id=DataEntryTypeEnum.scientific.value,
            carbon_report_module_id=10,
            data={"name": "Microscope"},
        )

        fake_factor = MagicMock()
        fake_factor.id = 3
        fake_factor.emission_type_id = EmissionType.equipment__scientific.value
        fake_factor.values = {}

        fake_comp = EmissionComputation(
            emission_type=EmissionType.equipment__scientific,
            formula_key="",
            quantity_key="",
        )

        with (
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[EmissionType.equipment__scientific],
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[fake_factor])
            ),
            patch.object(service, "_apply_formula", return_value=250.0),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type"
            ) as mock_handler_cls,
        ):
            mock_handler = MagicMock()
            mock_handler.kind_field = None
            mock_handler.pre_compute = AsyncMock(return_value={})
            mock_handler.resolve_computations = MagicMock(return_value=[fake_comp])
            mock_handler_cls.return_value = mock_handler

            results = await service.prepare_create(data_entry)

        # All rows should be leaf rows only
        rollup_rows = [
            r for r in results if r.emission_type_id in ROLLUP_EMISSION_TYPE_IDS
        ]
        assert rollup_rows == [], "Non-building types must not produce a rollup row"

    @pytest.mark.asyncio
    async def test_csv_override_with_multiple_factors_creates_single_row(self):
        """kg_co2eq override must not be duplicated per matching factor.

        The override is now passed via the ``kg_co2eq_override`` parameter
        rather than read from ``data_entry.data["kg_co2eq"]`` (which the new
        contract forbids — kg_co2eq must never live in the persisted column).
        """
        service = _make_service()

        data_entry = DataEntryResponse(
            id=102,
            data_entry_type_id=DataEntryTypeEnum.scientific.value,
            carbon_report_module_id=10,
            data={"name": "Microscope"},
        )

        fake_factor_1 = MagicMock()
        fake_factor_1.id = 11
        fake_factor_1.emission_type_id = EmissionType.equipment__scientific.value
        fake_factor_1.values = {"factor_kgco2eq": 1.0}

        fake_factor_2 = MagicMock()
        fake_factor_2.id = 12
        fake_factor_2.emission_type_id = EmissionType.equipment__scientific.value
        fake_factor_2.values = {"factor_kgco2eq": 2.0}

        fake_comp = EmissionComputation(
            emission_type=EmissionType.equipment__scientific,
            formula_key="factor_kgco2eq",
            quantity_key="units",
        )

        with (
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[EmissionType.equipment__scientific],
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(
                service,
                "_fetch_factors",
                new=AsyncMock(return_value=[fake_factor_1, fake_factor_2]),
            ),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type"
            ) as mock_handler_cls,
        ):
            mock_handler = MagicMock()
            mock_handler.kind_field = None
            mock_handler.pre_compute = AsyncMock(return_value={})
            mock_handler.resolve_computations = MagicMock(return_value=[fake_comp])
            mock_handler_cls.return_value = mock_handler

            results = await service.prepare_create(data_entry, kg_co2eq_override=300.0)

        assert len(results) == 1
        override_row = results[0]
        assert override_row.kg_co2eq == 300.0
        assert override_row.primary_factor_id is None
        assert len(override_row.meta["factors_used"]) == 2

    @pytest.mark.asyncio
    async def test_headcount_gets_rollup_row(self):
        service = _make_service()

        data_entry = DataEntryResponse(
            id=101,
            data_entry_type_id=DataEntryTypeEnum.member.value,
            carbon_report_module_id=10,
            data={"name": "Alice", "fte": 1.0},
        )

        leaf_types = [EmissionType.food, EmissionType.waste, EmissionType.commuting]
        fake_factor = MagicMock()
        fake_factor.id = 7
        fake_factor.emission_type_id = EmissionType.food.value
        fake_factor.values = {}

        fake_comp = EmissionComputation(
            emission_type=EmissionType.food,
            formula_key="",
            quantity_key="",
        )

        with (
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=leaf_types,
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[fake_factor])
            ),
            patch.object(service, "_apply_formula", return_value=100.0),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type"
            ) as mock_handler_cls,
        ):
            mock_handler = MagicMock()
            mock_handler.kind_field = None
            mock_handler.pre_compute = AsyncMock(return_value={})
            mock_handler.resolve_computations = MagicMock(return_value=[fake_comp])
            mock_handler_cls.return_value = mock_handler

            results = await service.prepare_create(data_entry)

        rollup_et = DATA_ENTRY_TYPE_TO_ROLLUP_EMISSION[DataEntryTypeEnum.member]
        rollup_rows = [r for r in results if r.emission_type_id == rollup_et.value]
        leaf_rows = [r for r in results if r.emission_type_id != rollup_et.value]

        assert len(rollup_rows) == 1
        rollup = rollup_rows[0]
        assert rollup.scope is None
        assert rollup.meta.get("is_rollup") is True
        assert rollup.kg_co2eq == pytest.approx(sum(r.kg_co2eq for r in leaf_rows))


# ---------------------------------------------------------------------------
# prepare_create — dynamic factor resolution (plan 1661)
#
# ``primary_factor_id`` is no longer read off the stored entry: the matching
# Factor is resolved on demand from the entry's classification fields via
# ``FactorResolver``, and the result — never the stored value — is what
# flows into the produced emission rows' ``primary_factor_id``.
# ---------------------------------------------------------------------------


class TestPrepareCreateResolvesFactorDynamically:
    @staticmethod
    def _mock_handler(kind_field: str) -> MagicMock:
        handler = MagicMock()
        handler.kind_field = kind_field
        handler.pre_compute = AsyncMock(return_value={})
        handler.resolve_computations = MagicMock(
            side_effect=lambda de, et, ctx: [
                EmissionComputation(
                    emission_type=et,
                    factor_id=ctx.get("primary_factor_id"),
                )
            ]
        )
        return handler

    @pytest.mark.asyncio
    async def test_prepare_create_resolves_factor_from_classification(self):
        """No primary_factor_id in data — the classification fields
        (kind/subkind) resolve the factor via FactorResolver, and its id is
        what the produced emission rows carry.
        """
        service = _make_service()

        factor = MagicMock(spec=Factor)
        factor.id = 42
        factor.emission_type_id = EmissionType.equipment__scientific.value
        factor.values = {"factor_kgco2eq": 1.5}

        resolver = MagicMock()
        resolver.resolve = AsyncMock(return_value=factor)

        de = DataEntryResponse(
            id=1,
            data_entry_type_id=DataEntryTypeEnum.scientific.value,
            carbon_report_module_id=10,
            data={"equipment_class": "microscope", "units": 2.0},
        )

        with (
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[factor])
            ),
            # #2050 J4: prepare_create primes the Strategy-B memo in one query
            # before the computation loop, which is its own DB seam.
            patch.object(
                service,
                "_prime_factor_query_cache",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(service, "_apply_formula", return_value=75.0),
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[EmissionType.equipment__scientific],
            ),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
                return_value=self._mock_handler("equipment_class"),
            ),
        ):
            results = await service.prepare_create(de, factor_resolver=resolver)

        assert len(results) == 1
        assert results[0].primary_factor_id == 42
        resolver.resolve.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_prepare_create_ignores_stale_stored_id(self):
        """A legacy row's stored primary_factor_id (999) must never win over
        the resolver's classification-based match (7) — the resolver result
        always wins, the stored value is dead weight.
        """
        service = _make_service()

        factor = MagicMock(spec=Factor)
        factor.id = 7
        factor.emission_type_id = EmissionType.equipment__scientific.value
        factor.values = {"factor_kgco2eq": 1.0}

        resolver = MagicMock()
        resolver.resolve = AsyncMock(return_value=factor)

        de = DataEntryResponse(
            id=2,
            data_entry_type_id=DataEntryTypeEnum.scientific.value,
            carbon_report_module_id=10,
            data={
                "equipment_class": "microscope",
                "units": 2.0,
                "primary_factor_id": 999,  # stale legacy value — must be ignored
            },
        )

        with (
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[factor])
            ),
            # #2050 J4: prepare_create primes the Strategy-B memo in one query
            # before the computation loop, which is its own DB seam.
            patch.object(
                service,
                "_prime_factor_query_cache",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(service, "_apply_formula", return_value=50.0),
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[EmissionType.equipment__scientific],
            ),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
                return_value=self._mock_handler("equipment_class"),
            ),
        ):
            results = await service.prepare_create(de, factor_resolver=resolver)

        assert len(results) == 1
        assert results[0].primary_factor_id == 7
        assert results[0].primary_factor_id != 999

    @pytest.mark.asyncio
    async def test_building_energy_type_from_resolved_factor(self):
        """Building entry with no stored id: the resolver-matched factor's
        classification.energy_type selects the single heating leaf (#1575)
        end to end through resolve -> _get_building_energy_type ->
        resolve_emission_types (mirrors the #1575 rollup test, minus the
        stored id).
        """
        service = _make_service()

        factor = MagicMock(spec=Factor)
        factor.id = 5
        factor.classification = {"energy_type": "electric"}
        factor.emission_type_id = EmissionType.buildings__rooms__heating_electric.value
        factor.values = {}

        resolver = MagicMock()
        resolver.resolve = AsyncMock(return_value=factor)

        de = DataEntryResponse(
            id=3,
            data_entry_type_id=DataEntryTypeEnum.building.value,
            carbon_report_module_id=10,
            # room_name is required since #2501 — an incomplete row resolves
            # to no leaves, and this test needs the real resolver to fire.
            data={
                "building_name": "B1",
                "room_name": "BCH 1234",
                "room_type": "office",
            },
        )

        with (
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[factor])
            ),
            # #2050 J4: prepare_create primes the Strategy-B memo in one query
            # before the computation loop, which is its own DB seam.
            patch.object(
                service,
                "_prime_factor_query_cache",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(service, "_apply_formula", return_value=100.0),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
                return_value=self._mock_handler("building_name"),
            ),
        ):
            results = await service.prepare_create(de, factor_resolver=resolver)

        heating_leaf_ids = {
            EmissionType.buildings__rooms__heating_electric__office.value,
            EmissionType.buildings__rooms__heating_thermal__office.value,
        }
        produced_heating = {
            r.emission_type_id
            for r in results
            if r.emission_type_id in heating_leaf_ids
        }
        assert produced_heating == {
            EmissionType.buildings__rooms__heating_electric__office.value
        }


# ---------------------------------------------------------------------------
# _fetch_factors — Strategy B query cache (recalc N+1 fix)
# ---------------------------------------------------------------------------


class TestFetchFactorsStrategyBCache:
    """Strategy B hits the DB per computation; a slice-scoped query cache
    collapses the per-entry N+1 that dominated headcount recalc.
    """

    def _comp(self):
        from app.models.data_entry_emission import (
            EmissionComputation,
            FactorQuery,
        )
        from app.modules.emissions import EmissionType

        return EmissionComputation(
            emission_type=EmissionType.food,
            factor_query=FactorQuery(
                data_entry_type=DataEntryTypeEnum.member,
                kind="food",
            ),
        )

    @pytest.mark.asyncio
    async def test_cache_hit_queries_db_once(self):
        service = _make_service()
        comp = self._comp()
        fake_factor = MagicMock()
        get_by_classification = AsyncMock(return_value=fake_factor)
        with patch(
            "app.services.data_entry_emission_service.FactorService"
        ) as mock_fs_cls:
            mock_fs_cls.return_value = MagicMock(
                get_by_classification=get_by_classification
            )
            cache: dict = {}
            r1 = await service._fetch_factors(comp, 2026, factor_query_cache=cache)
            r2 = await service._fetch_factors(comp, 2026, factor_query_cache=cache)

        assert r1 == [fake_factor]
        assert r2 == r1
        # Two identical Strategy-B lookups → one DB query.
        get_by_classification.assert_awaited_once()
        assert len(cache) == 1

    @pytest.mark.asyncio
    async def test_no_cache_queries_each_call(self):
        service = _make_service()
        comp = self._comp()
        get_by_classification = AsyncMock(return_value=MagicMock())
        with patch(
            "app.services.data_entry_emission_service.FactorService"
        ) as mock_fs_cls:
            mock_fs_cls.return_value = MagicMock(
                get_by_classification=get_by_classification
            )
            await service._fetch_factors(comp, 2026)
            await service._fetch_factors(comp, 2026)

        # Without the opt-in cache, behaviour is unchanged: one query per call.
        assert get_by_classification.await_count == 2


# ---------------------------------------------------------------------------
# Factor-year resolution — reference_year wins (Simulator Plan)
# ---------------------------------------------------------------------------


class TestFactorYearResolution:
    """Plan-year reports source factors from their reference year."""

    @staticmethod
    def _report(year, reference_year):
        report = MagicMock()
        report.year = year
        report.reference_year = reference_year
        report.carbon_project_id = None
        return report

    @pytest.mark.asyncio
    async def test_plan_report_uses_reference_year(self):
        service = _make_service()
        de = _make_data_entry_response({})
        with patch.object(
            service,
            "_get_report_for_data_entry",
            new=AsyncMock(return_value=self._report(2027, 2024)),
        ):
            assert await service._get_year_from_data_entry(de) == 2024

    @pytest.mark.asyncio
    async def test_calculator_report_uses_year(self):
        service = _make_service()
        de = _make_data_entry_response({})
        with patch.object(
            service,
            "_get_report_for_data_entry",
            new=AsyncMock(return_value=self._report(2025, None)),
        ):
            assert await service._get_year_from_data_entry(de) == 2025


# ---------------------------------------------------------------------------
# Planner headcount — full emissions from aggregate FTE via member factors
# ---------------------------------------------------------------------------


class TestPlannerHeadcountEmissions:
    """Simulator Plan headcount rows compute fte × member factor."""

    @pytest.mark.asyncio
    async def test_planner_headcount_computes_from_member_factor(self):
        service = _make_service()
        factor = MagicMock(spec=Factor)
        factor.id = 7
        factor.emission_type_id = EmissionType.food__vegetarian.value
        factor.values = {
            "ef_kg_co2eq_per_unit": 2.0,
            "number_of_unit_per_fte": 100.0,
            "unit": "kg",
        }
        de = DataEntryResponse(
            id=3,
            data_entry_type_id=DataEntryTypeEnum.planner_headcount.value,
            carbon_report_module_id=10,
            data={"sius_code": "51", "fte": 4.5},
        )

        with (
            patch.object(
                service, "_fetch_factors", new=AsyncMock(return_value=[factor])
            ),
            # #2050 J4: prepare_create primes the Strategy-B memo in one query
            # before the computation loop, which is its own DB seam.
            patch.object(
                service,
                "_prime_factor_query_cache",
                new=AsyncMock(return_value=None),
            ),
            patch.object(
                service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
            ),
            patch.object(
                service,
                "_get_report_for_data_entry",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "app.services.data_entry_emission_service.resolve_emission_types",
                return_value=[EmissionType.food],
            ),
            patch(
                "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
            ) as mock_handler_cls,
        ):
            mock_handler = PlannerHeadcountModuleHandler()
            mock_handler.pre_compute = AsyncMock(return_value={})
            mock_handler_cls.return_value = mock_handler

            results = await service.prepare_create(de)

        assert len(results) == 1
        # fte (4.5, aggregate > 1 allowed) × ef (2.0) × units/fte (100)
        assert results[0].kg_co2eq == pytest.approx(900.0)

    def test_planner_headcount_create_allows_aggregate_fte(self):
        dto = PlannerHeadCountCreate(
            data_entry_type_id=DataEntryTypeEnum.planner_headcount.value,
            carbon_report_module_id=1,
            sius_code="51",
            fte=12.5,
        )
        assert dto.data["fte"] == 12.5

    def test_planner_headcount_create_rejects_unknown_sius_code(self):
        with pytest.raises(ValueError):
            PlannerHeadCountCreate(
                data_entry_type_id=DataEntryTypeEnum.planner_headcount.value,
                carbon_report_module_id=1,
                sius_code="99",
                fte=1.0,
            )


# ---------------------------------------------------------------------------
# Percentage override — planner snapshot source_data_entry_id matching
# ---------------------------------------------------------------------------


class TestPercentageOverrideSnapshotSource:
    """Snapshot entries match their exact source entry, not name heuristics."""

    @staticmethod
    def _report():
        report = MagicMock()
        report.year = 2027
        report.reference_year = 2024
        report.unit_id = 1
        return report

    @pytest.mark.asyncio
    async def test_source_entry_id_scales_source_emissions(self):
        service = _make_service()
        de = DataEntryResponse(
            id=9,
            data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
            carbon_report_module_id=10,
            data={
                "quantity_kg": 5.0,
                "percentage_of_reference_year": 40,
                "source_data_entry_id": 123,
            },
        )
        service.session.get = AsyncMock(return_value=MagicMock(id=123))
        # Source resolves to a report of the same unit (ownership gate passes).
        with (
            patch.object(
                service,
                "_sum_entry_emissions",
                new=AsyncMock(return_value=(200.0, 77)),
            ),
            patch.object(
                service,
                "_get_report_for_data_entry",
                new=AsyncMock(return_value=MagicMock(unit_id=1)),
            ),
        ):
            result = await service._get_percentage_override_kg(
                de, EmissionType.process_emissions, self._report()
            )
        # 40% of the source's 200kg, and the source leaf's factor id travels
        # with it so the copied row keeps its provenance (plan #2050 F3).
        assert result is not None
        kg, factor_id = result
        assert kg == pytest.approx(80.0)
        assert factor_id == 77
        service.session.get.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_deleted_source_falls_back_to_normal_compute(self):
        service = _make_service()
        de = DataEntryResponse(
            id=9,
            data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
            carbon_report_module_id=10,
            data={
                "quantity_kg": 5.0,
                "percentage_of_reference_year": 40,
                "source_data_entry_id": 123,
            },
        )
        service.session.get = AsyncMock(return_value=None)
        result = await service._get_percentage_override_kg(
            de, EmissionType.process_emissions, self._report()
        )
        # None → prepare_create computes from the snapshot data instead.
        assert result is None

    @pytest.mark.asyncio
    async def test_cross_unit_source_is_rejected(self):
        """A crafted source_data_entry_id pointing at another unit is ignored."""
        service = _make_service()
        de = DataEntryResponse(
            id=9,
            data_entry_type_id=DataEntryTypeEnum.process_emissions.value,
            carbon_report_module_id=10,
            data={
                "quantity_kg": 5.0,
                "percentage_of_reference_year": 40,
                "source_data_entry_id": 999,
            },
        )
        service.session.get = AsyncMock(return_value=MagicMock(id=999))
        with (
            patch.object(
                service,
                "_sum_entry_emissions",
                new=AsyncMock(return_value=(1_000.0, 5)),
            ) as sum_mock,
            patch.object(
                service,
                "_get_report_for_data_entry",
                # Source belongs to unit 2, report is unit 1 → rejected.
                new=AsyncMock(return_value=MagicMock(unit_id=2)),
            ),
        ):
            result = await service._get_percentage_override_kg(
                de, EmissionType.process_emissions, self._report()
            )
        assert result is None
        sum_mock.assert_not_awaited()


# ---------------------------------------------------------------------------
# #2050 Track J — prepare_create fails hard instead of publishing a
# wrong-but-plausible number
# ---------------------------------------------------------------------------
#
# Each of these sites used to log and carry on. The guardrails call that a
# silent fallback ("a log line nobody reads is a silent fallback"), and the
# failure mode is the worst one this project has: a total that looks
# complete but is missing a leaf, priced off the wrong year's factor, or
# silently zero. The recalc workflow already contains per-entry failures
# (emission_recalculation.py:173-210 records them in ``error_details`` and
# continues the batch), so raising here surfaces the problem without
# stalling the pipeline.


def _emission_computation(**kwargs) -> EmissionComputation:
    defaults = {
        "emission_type": EmissionType.professional_travel__plane,
        "factor_id": 99,
    }
    return EmissionComputation(**{**defaults, **kwargs})


@contextmanager
def _patched_handler(computations: list[EmissionComputation]):
    """Patch BaseModuleHandler.get_by_type with a handler returning
    ``computations`` — the shape every prepare_create test below needs.
    """
    with patch(
        "app.services.data_entry_emission_service.BaseModuleHandler.get_by_type",
    ) as mock_handler_cls:
        mock_handler = MagicMock()
        mock_handler.kind_field = None
        mock_handler.pre_compute = AsyncMock(return_value={})
        mock_handler.resolve_computations = MagicMock(return_value=computations)
        mock_handler_cls.return_value = mock_handler
        yield mock_handler_cls


@pytest.mark.asyncio
async def test_prepare_create_raises_when_a_formula_returns_none():
    """#2050 Track J: the leaf-dropping fallback that started this.

    A factor missing the key the formula needs used to log a warning and
    ``continue``, so an entry declaring three leaves silently produced
    fewer. Downstream that shows up as a plausible total that is simply
    too low — and, for headcount types, as a missing rollup row (the
    rollup is only written when more than one leaf survives), which
    renders as a blank cell rather than a visible error.
    """
    service = _make_service()

    factor = MagicMock(spec=Factor)
    factor.id = 99
    factor.year = 2024
    factor.emission_type_id = EmissionType.professional_travel__plane.value
    # No ``ef_kg_co2eq_per_unit`` — the formula cannot resolve.
    factor.values = {"unit": "km"}

    de = _make_data_entry_response({"distance_km": 100})

    with (
        patch.object(service, "_fetch_factors", new=AsyncMock(return_value=[factor])),
        patch.object(
            service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
        ),
        patch(
            "app.services.data_entry_emission_service.resolve_emission_types",
            return_value=[EmissionType.professional_travel__plane],
        ),
        _patched_handler(
            [
                _emission_computation(
                    formula_key="ef_kg_co2eq_per_unit", quantity_key="distance_km"
                )
            ]
        ),
        pytest.raises(ValueError, match="ef_kg_co2eq_per_unit"),
    ):
        await service.prepare_create(de)


@pytest.mark.asyncio
async def test_prepare_create_raises_on_unhandled_data_entry_type():
    """#2050 Track J: an unmapped type used to return [] — zero emissions,
    indistinguishable from an entry that genuinely emits nothing.
    """
    service = _make_service()
    de = _make_data_entry_response({"distance_km": 100})

    with (
        patch.object(
            service, "_get_year_from_data_entry", new=AsyncMock(return_value=2024)
        ),
        patch(
            "app.services.data_entry_emission_service.resolve_emission_types",
            return_value=None,
        ),
        _patched_handler([_emission_computation()]),
        pytest.raises(ValueError, match="No emission types are mapped"),
    ):
        await service.prepare_create(de)


@pytest.mark.asyncio
async def test_prepare_create_raises_when_year_cannot_be_determined():
    """#2050 Track J: this site logged "factors may not match" and then
    used the mismatched factors anyway — it named its own defect in the
    log line and carried on.
    """
    service = _make_service()
    de = _make_data_entry_response({"distance_km": 100})

    with (
        patch.object(
            service, "_get_year_from_data_entry", new=AsyncMock(return_value=None)
        ),
        patch.object(
            service, "_get_report_for_data_entry", new=AsyncMock(return_value=None)
        ),
        _patched_handler([_emission_computation()]),
        pytest.raises(ValueError, match="year"),
    ):
        await service.prepare_create(de)


@pytest.mark.asyncio
async def test_fetch_factors_raises_when_the_factor_is_the_wrong_year():
    """#2050 Track J: a factor from the wrong year made ``_fetch_factors``
    return [], so the leaf loop never ran — a silent zero that also slips
    past the missing-key raise, because there is no factor left to fail on.
    """
    service = _make_service()

    factor = MagicMock(spec=Factor)
    factor.id = 99
    factor.year = 2023  # entry is 2024
    factor.values = {"ef_kg_co2eq_per_unit": 0.5}

    with (
        patch(
            "app.services.data_entry_emission_service.FactorService"
        ) as factor_service_cls,
        pytest.raises(ValueError, match="year"),
    ):
        factor_service_cls.return_value.get = AsyncMock(return_value=factor)
        await service._fetch_factors(_emission_computation(factor_id=99), year=2024)


@pytest.mark.asyncio
async def test_fetch_factors_raises_when_a_referenced_factor_is_missing():
    """#2050 Track J: the quietest site of all — a computation naming a
    factor_id that resolves to nothing returned [] with no log line at
    all, so the entry contributed zero and left no evidence.
    """
    service = _make_service()

    with (
        patch(
            "app.services.data_entry_emission_service.FactorService"
        ) as factor_service_cls,
        pytest.raises(ValueError, match="12345"),
    ):
        factor_service_cls.return_value.get = AsyncMock(return_value=None)
        await service._fetch_factors(_emission_computation(factor_id=12345), year=2024)


@pytest.mark.asyncio
async def test_prime_factor_query_cache_seeds_every_b3_criteria_in_one_query():
    """#2050 J4: three emission roots meant three subtree queries. Priming the
    memo the bulk paths already pass collapses them into one.
    """
    service = _make_service()

    food = MagicMock(spec=Factor)
    food.id = 1
    food.emission_type_id = EmissionType.food__vegetarian.value
    food.data_entry_type_id = DataEntryTypeEnum.member.value
    commuting = MagicMock(spec=Factor)
    commuting.id = 2
    commuting.emission_type_id = EmissionType.commuting__cycling.value
    commuting.data_entry_type_id = DataEntryTypeEnum.member.value

    comps = [
        _emission_computation(
            emission_type=EmissionType.food,
            factor_id=None,
            factor_query=FactorQuery(
                data_entry_type=DataEntryTypeEnum.member,
                emission_type=EmissionType.food,
            ),
        ),
        _emission_computation(
            emission_type=EmissionType.commuting,
            factor_id=None,
            factor_query=FactorQuery(
                data_entry_type=DataEntryTypeEnum.member,
                emission_type=EmissionType.commuting,
            ),
        ),
    ]

    with patch(
        "app.services.data_entry_emission_service.FactorService"
    ) as factor_service_cls:
        list_mock = AsyncMock(return_value=[food, commuting])
        factor_service_cls.return_value.list_by_emission_types = list_mock
        cache: dict = {}
        await service._prime_factor_query_cache(
            comps, year=2025, factor_query_cache=cache
        )

    # One query covering both subtrees, not one per root.
    assert list_mock.await_count == 1
    # And both criteria are now answerable from the memo, so _fetch_factors
    # issues nothing for them.
    assert len(cache) == 2
    assert {f.id for factors in cache.values() for f in factors} == {1, 2}


@pytest.mark.asyncio
async def test_prime_factor_query_cache_key_matches_what_fetch_factors_reads():
    """The prime is useless if its key differs from the memo key
    ``_fetch_factors`` looks up — pin that they are the same tuple.
    """
    service = _make_service()
    query = FactorQuery(
        data_entry_type=DataEntryTypeEnum.member,
        emission_type=EmissionType.food,
    )
    comp = _emission_computation(
        emission_type=EmissionType.food, factor_id=None, factor_query=query
    )

    with patch(
        "app.services.data_entry_emission_service.FactorService"
    ) as factor_service_cls:
        factor_service_cls.return_value.list_by_emission_types = AsyncMock(
            return_value=[]
        )
        cache: dict = {}
        await service._prime_factor_query_cache(
            [comp], year=2025, factor_query_cache=cache
        )

    assert service._factor_query_cache_key(query, 2025) in cache
