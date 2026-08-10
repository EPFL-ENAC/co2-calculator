from typing import Any, Optional

from sqlalchemy.orm import aliased
from sqlmodel import col, select

from app.core.logging import get_logger
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.data_entry_emission import (
    DataEntryEmission,
    EmissionComputation,
    FactorQuery,
)
from app.models.module_type import ModuleTypeEnum
from app.modules.professional_travel.data_entries import (
    ProfessionalTravelPlaneHandlerCreate,
    ProfessionalTravelPlaneHandlerResponse,
    ProfessionalTravelPlaneHandlerUpdate,
    ProfessionalTravelTrainHandlerCreate,
    ProfessionalTravelTrainHandlerResponse,
    ProfessionalTravelTrainHandlerUpdate,
)
from app.schemas.data_entry import (
    BaseModuleHandler,
    DataEntryCreate,
    DataEntryResponseGen,
    DataEntryUpdate,
)
from app.services.factor_service import FactorService
from app.services.location_service import LocationService
from app.utils.distance_geography import (
    _determine_train_countrycode,
    calculate_plane_distance,
    calculate_train_distance,
    get_haul_category,
)
from app.utils.factor_year import resolve_factor_year

logger = get_logger(__name__)

MemberEntry = aliased(DataEntry)


async def _get_report_year_for_module(
    session: Any,
    carbon_report_module_id: int | None,
) -> int | None:
    """Resolve the calculation year for factor lookups on a data entry."""
    if carbon_report_module_id is None:
        return None
    stmt = (
        select(CarbonReport)
        .join(
            CarbonReportModule,
            col(CarbonReportModule.carbon_report_id) == col(CarbonReport.id),
        )
        .where(col(CarbonReportModule.id) == carbon_report_module_id)
    )
    result = await session.exec(stmt)
    report = result.one_or_none()
    if report is None:
        return None
    return await resolve_factor_year(session, report)


class ProfessionalTravelBaseModuleHandler(BaseModuleHandler):
    module_type: ModuleTypeEnum = ModuleTypeEnum.professional_travel
    data_entry_type: DataEntryTypeEnum
    create_dto: type[DataEntryCreate]
    update_dto: type[DataEntryUpdate]
    response_dto: type[DataEntryResponseGen]

    kind_field: Optional[str] = None
    subkind_field: Optional[str] = None
    require_subkind_for_factor = False
    require_factor_to_match = False

    sort_map = {
        "id": DataEntry.id,
        "departure_date": DataEntry.data["departure_date"].as_string(),
        "cabin_class": DataEntry.data["cabin_class"].as_string(),
        "number_of_trips": DataEntry.data["number_of_trips"].as_float(),
        "traveler_name": MemberEntry.data["name"].as_string(),
        "kg_co2eq": DataEntryEmission.kg_co2eq,
        # Plane destination
        "origin_iata": DataEntry.data["origin_iata"].as_string(),
        "destination_iata": DataEntry.data["destination_iata"].as_string(),
    }

    def to_response(
        self,
        data_entry: DataEntry,
        enriched_data: dict | None = None,
    ) -> DataEntryResponseGen:
        data = enriched_data if enriched_data is not None else data_entry.data
        return self.response_dto.model_validate(
            {
                "id": data_entry.id,
                "data_entry_type_id": data_entry.data_entry_type_id,
                "carbon_report_module_id": data_entry.carbon_report_module_id,
                **data,
            }
        )

    def validate_create(self, payload: dict) -> DataEntryCreate:
        return self.create_dto.model_validate(payload)

    def validate_update(self, payload: dict) -> DataEntryUpdate:
        return self.update_dto.model_validate(payload)


class ProfessionalTravelPlaneModuleHandler(ProfessionalTravelBaseModuleHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.plane
    create_dto = ProfessionalTravelPlaneHandlerCreate
    update_dto = ProfessionalTravelPlaneHandlerUpdate
    response_dto = ProfessionalTravelPlaneHandlerResponse

    kind_field: str = "category"
    subkind_field: str = "cabin_class"

    filter_map = {
        "origin_iata": DataEntry.data["origin_iata"].as_string(),
        "destination_iata": DataEntry.data["destination_iata"].as_string(),
    }

    async def prefetch_slice(
        self,
        entries: list[Any],
        session: Any,
        *,
        year: int | None = None,
    ) -> dict:
        """Bulk-load the slice's airports + plane factors once per recalc.

        Without this, ``pre_compute`` does two airport point-lookups, a year
        lookup and a full plane-factor reload *per entry* — ~4 DB round-trips
        × every flight in the slice. All three are constant across a
        ``(plane, year)`` slice, so we resolve them here in two queries and
        ``pre_compute`` reads them in-memory. Returns ``{}`` when the slice
        has no year (``pre_compute`` then keeps its per-entry fallback).
        """
        if year is None:
            return {}
        iata_codes: set[str] = set()
        for entry in entries:
            origin = entry.data.get("origin_iata")
            destination = entry.data.get("destination_iata")
            if origin:
                iata_codes.add(origin)
            if destination:
                iata_codes.add(destination)
        locations = await LocationService(session).get_locations_by_iata(
            list(iata_codes)
        )
        plane_factors = await FactorService(session).list_by_data_entry_type(
            DataEntryTypeEnum.plane,
            year=year,
        )
        return {
            "locations": {loc.iata_code: loc for loc in locations},
            "plane_factors": plane_factors,
            "year": year,
        }

    async def pre_compute(
        self, data_entry: Any, session: Any, *, slice_cache: dict | None = None
    ) -> dict:
        """Compute flight distance and haul category
        from origin/destination airports.

        ``slice_cache`` (from ``prefetch_slice``) supplies airports, year and
        plane factors in-memory during a recalc; absent it (single-entry
        create/update), the per-entry DB lookups below run unchanged.
        """
        origin_iata = data_entry.data.get("origin_iata")
        destination_iata = data_entry.data.get("destination_iata")
        number_of_trips = data_entry.data.get("number_of_trips", 1)
        if origin_iata is None or destination_iata is None:
            # Entry persists but produces no emission leaves —
            # "skip, don't default" semantic.  Log so an operator
            # tracking missing-IATA uploads can find them without
            # querying the DB directly.
            logger.warning(
                "plane.pre_compute: skipping entry id=%s — missing "
                "origin_iata or destination_iata (origin=%r, destination=%r)",
                getattr(data_entry, "id", None),
                origin_iata,
                destination_iata,
            )
            return {}

        origin, dest = await self._lookup_airports(
            session, origin_iata, destination_iata, slice_cache
        )
        if not origin or not dest:
            logger.warning(
                "plane.pre_compute: skipping entry id=%s — IATA not found "
                "in locations table (origin_iata=%r resolved=%s, "
                "destination_iata=%r resolved=%s)",
                getattr(data_entry, "id", None),
                origin_iata,
                origin is not None,
                destination_iata,
                dest is not None,
            )
            return {}
        distance_one_trip_km = calculate_plane_distance(
            origin_airport=origin,
            dest_airport=dest,
        )
        if distance_one_trip_km is None:
            logger.warning(
                "plane.pre_compute: skipping entry id=%s — distance "
                "calculation returned None (origin_iata=%r, destination_iata=%r)",
                getattr(data_entry, "id", None),
                origin_iata,
                destination_iata,
            )
            return {}
        year, plane_factors = await self._year_and_plane_factors(
            session, data_entry, slice_cache
        )
        haul_category = get_haul_category(distance_one_trip_km, plane_factors)
        if haul_category is None:
            logger.warning(
                "plane.pre_compute: skipping entry id=%s — no haul band matches "
                "distance %s km for year=%s",
                getattr(data_entry, "id", None),
                distance_one_trip_km,
                year,
            )
            return {}
        distance_km = distance_one_trip_km * number_of_trips
        return {
            "distance_one_trip_km": distance_one_trip_km,
            "haul_category": haul_category,
            "distance_km": distance_km,
        }

    async def _lookup_airports(
        self,
        session: Any,
        origin_iata: str,
        destination_iata: str,
        slice_cache: dict | None,
    ) -> tuple[Any, Any]:
        """Origin/destination ``Location`` from the slice cache, else two
        per-entry point lookups (single-entry path)."""
        if slice_cache is not None:
            locations = slice_cache["locations"]
            return locations.get(origin_iata), locations.get(destination_iata)
        loc_service = LocationService(session)
        return (
            await loc_service.get_location_by_iata(origin_iata),
            await loc_service.get_location_by_iata(destination_iata),
        )

    async def _year_and_plane_factors(
        self,
        session: Any,
        data_entry: Any,
        slice_cache: dict | None,
    ) -> tuple[int | None, list]:
        """Slice year + plane factors from the cache, else per-entry lookups."""
        if slice_cache is not None:
            return slice_cache["year"], slice_cache["plane_factors"]
        year = await _get_report_year_for_module(
            session, data_entry.carbon_report_module_id
        )
        plane_factors = await FactorService(session).list_by_data_entry_type(
            DataEntryTypeEnum.plane,
            year=year,
        )
        return year, plane_factors

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:

        # cabin_class = data_entry.data.get("cabin_class")
        haul_category = ctx.get("haul_category")
        # context: dict = {}
        if haul_category is None:
            logger.warning(
                f"Haul category could not be determined for data entry {data_entry.id}"
            )
            haul_category = "unknown"
        cabin_class = data_entry.data.get("cabin_class")
        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.plane,
                    kind=haul_category,
                    subkind=cabin_class,
                    context={},
                ),
                formula_key="ef_kg_co2eq_per_km",
                quantity_key="distance_km",
                multiplier_key="rfi_adjustment",
                multiplier_default=1.0,
            )
        ]


class ProfessionalTravelTrainModuleHandler(ProfessionalTravelBaseModuleHandler):
    data_entry_type: DataEntryTypeEnum = DataEntryTypeEnum.train
    create_dto = ProfessionalTravelTrainHandlerCreate
    update_dto = ProfessionalTravelTrainHandlerUpdate
    response_dto = ProfessionalTravelTrainHandlerResponse

    filter_map = {
        "origin_name": DataEntry.data["origin_name"].as_string(),
        "destination_name": DataEntry.data["destination_name"].as_string(),
    }

    async def enrich_csv_row(
        self,
        data: dict,
        session: Any,
    ) -> tuple[dict, Optional[str]]:
        """Resolve ``origin_name`` / ``destination_name`` → ``*_natural_key``.

        Train CSVs ship a ``{role}_country_code`` column to disambiguate
        same-name stations across countries (e.g. Bern, CH vs Berne, DE).
        It is **required**: a row missing it for either endpoint is rejected
        before any station lookup — there is no ``CH`` default. The
        ``stations.csv``-derived seed carries country codes natively.

        UI/API entries already carry ``*_natural_key`` (sent directly from
        the station autocomplete) — the hook leaves those rows alone.

        Resolution failure modes split:
          - missing country_code: row fails — operator must supply it.
          - ambiguous (>1 match): row fails — operator must hand-curate the
            upstream data (or pick a more specific name).
          - not_found (0 matches): mirror the plane unknown-IATA path —
            persist the entry without ``natural_key``; ``pre_compute`` logs
            a WARNING and skips emission. Operator sees the gap in
            entry-vs-emission counts.
        """
        enriched = dict(data)
        loc_service = LocationService(session)
        for role in ("origin", "destination"):
            if enriched.get(f"{role}_natural_key"):
                continue
            name = enriched.get(f"{role}_name")
            if not name:
                return data, f"Missing {role}_name"
            # Canonicalize to uppercase: the seed stores ISO-2 codes uppercase
            # and the station lookup matches country_code exactly.
            country_code = (enriched.get(f"{role}_country_code") or "").strip().upper()
            if not country_code:
                return (
                    data,
                    f"Missing {role}_country_code (required for train CSV ingestion)",
                )
            station, reason = await loc_service.resolve_train_station_for_csv(
                name=name,
                country_code=country_code,
            )
            if station is not None:
                enriched[f"{role}_natural_key"] = station.natural_key
                continue
            if reason.startswith("ambiguous"):
                return (
                    data,
                    f"{role} station {name!r} in {country_code}: {reason} "
                    f"— supply {role}_country_code or fix the upstream data",
                )
            logger.warning(
                "Train CSV row: %s station %r not found in locations table "
                "(country_code=%s). Entry will persist but emission cannot "
                "be computed.",
                role,
                name,
                country_code,
            )
        return enriched, None

    async def pre_compute(self, data_entry: Any, session: Any) -> dict:
        """Compute train distance and determine relevant country code."""
        origin_name = data_entry.data.get("origin_name")
        destination_name = data_entry.data.get("destination_name")
        origin_natural_key = data_entry.data.get("origin_natural_key")
        destination_natural_key = data_entry.data.get("destination_natural_key")
        number_of_trips = data_entry.data.get("number_of_trips", 1)
        if origin_name is None or destination_name is None:
            logger.warning(
                "train.pre_compute: skipping entry id=%s — missing "
                "origin_name or destination_name (origin=%r, destination=%r)",
                getattr(data_entry, "id", None),
                origin_name,
                destination_name,
            )
            return {}
        if not origin_natural_key or not destination_natural_key:
            # Should not happen on the CSV path — ``enrich_csv_row`` fills these
            # in at ingest time. The UI path always sends them. Logging at
            # WARNING so a silent recurrence is visible in operator dashboards
            # instead of surfacing only as zero emissions downstream.
            logger.warning(
                "Train data_entry id=%s missing natural_keys "
                "(origin=%r, destination=%r); no distance/emission computed.",
                data_entry.id,
                origin_natural_key,
                destination_natural_key,
            )
            return {}

        loc_service = LocationService(session)
        origin = await loc_service.get_location_by_natural_key(origin_natural_key)
        dest = await loc_service.get_location_by_natural_key(destination_natural_key)

        if origin is None or dest is None:
            logger.warning(
                "train.pre_compute: skipping entry id=%s — natural_key "
                "not found in locations table (origin_key=%r resolved=%s, "
                "destination_key=%r resolved=%s)",
                getattr(data_entry, "id", None),
                origin_natural_key,
                origin is not None,
                destination_natural_key,
                dest is not None,
            )
            return {}
        distance_one_trip_km = calculate_train_distance(
            origin_station=origin,
            dest_station=dest,
        )
        if distance_one_trip_km is None:
            logger.warning(
                "train.pre_compute: skipping entry id=%s — distance "
                "calculation returned None (origin_natural_key=%r, "
                "destination_natural_key=%r)",
                getattr(data_entry, "id", None),
                origin_natural_key,
                destination_natural_key,
            )
            return {}
        distance_km = distance_one_trip_km * number_of_trips

        country_code = _determine_train_countrycode(origin, dest)
        return {
            "distance_km": distance_km,
            "distance_one_trip_km": distance_one_trip_km,
            "country_code": country_code,
        }

    def resolve_computations(
        self, data_entry: Any, emission_type: Any, ctx: dict
    ) -> list:
        country_code = ctx.get("country_code") or None
        # todo check that fallbacks works! it was not the case!

        return [
            EmissionComputation(
                emission_type=emission_type,
                factor_query=FactorQuery(
                    data_entry_type=DataEntryTypeEnum.train,
                    # Train factors are keyed by country_code in classification.
                    # Fall back to RoW if the exact country is not found.
                    kind=None,
                    subkind=None,
                    context={"country_code": country_code},
                    fallbacks={"country_code": "RoW"},
                ),
                formula_key="ef_kg_co2eq_per_km",
                quantity_key="distance_km",
            )
        ]
