"""Professional Travel service for business logic."""

import asyncio
from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple, Union

from fastapi import HTTPException, status
from sqlalchemy import and_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.location import Location
from app.models.professional_travel import (
    ProfessionalTravel,
    ProfessionalTravelCreate,
    ProfessionalTravelEmission,
    ProfessionalTravelItemResponse,
    ProfessionalTravelUpdate,
)
from app.models.user import User
from app.repositories.professional_travel_repo import ProfessionalTravelRepository
from app.schemas.equipment import (
    ModuleResponse,
    ModuleTotals,
    SubmoduleResponse,
    SubmoduleSummary,
)
from app.services.travel_calculation_service import TravelCalculationService

logger = get_logger(__name__)


async def can_user_edit_item(travel: ProfessionalTravel, user: User) -> bool:
    """
    Check if user can edit a professional travel item using OPA resource access policy.

    This function has been migrated from role-based checks to permission-based
    resource access policy evaluation.

    Args:
        travel: Professional travel record
        user: Current user

    Returns:
        True if user can edit, False otherwise

    Rules (enforced via OPA policy):
        - API trips are read-only for everyone
        - Principals and secondaries can edit manual/CSV trips in their units
        - Standard users can only edit their own manual trips
        - Backoffice admins can edit all trips
    """
    from app.services.authorization_service import check_resource_access

    # Build resource dict for policy evaluation
    resource = {
        "id": travel.id,
        "created_by": travel.created_by,
        "unit_id": travel.unit_id,
        "provider": travel.provider,
    }

    # Use OPA policy for resource access check
    return await check_resource_access(
        user, "professional_travel", resource, action="edit"
    )


class ProfessionalTravelService:
    """Service for professional travel business logic."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = ProfessionalTravelRepository(session)

    async def bulk_insert_travel_entries(
        self, entries: List[dict[str, Any]]
    ) -> List[ProfessionalTravel]:
        """Bulk insert professional travel entries."""
        return await self.repo.bulk_insert_travel_entries(entries)

    async def _validate_traveler(
        self, traveler_id: Optional[int], traveler_name: str, unit_id: int
    ) -> Optional[int]:
        """
        Traveler name is a free-text field, no validation against headcount.
        Always returns None for traveler_id.

        Args:
            traveler_id: Traveler ID (optional, not used)
            traveler_name: Traveler display name (free-text, not validated)
            unit_id: Unit ID (not used)

        Returns:
            None - traveler_id is always None
        """
        # No validation, traveler_name is free-text
        # Parameters kept for backward compatibility with existing call sites
        return None

    async def _get_travel_item_response(
        self, travel: ProfessionalTravel, user: User
    ) -> ProfessionalTravelItemResponse:
        """
        Get item response for a single travel with related data fetched.

        Args:
            travel: Professional travel record
            user: Current user

        Returns:
            ProfessionalTravelItemResponse with all related data populated
        """
        # Fetch related data for this single travel
        origin_locations, dest_locations, emissions = await self._fetch_related_data(
            [travel]
        )

        return await self._to_item_response(
            travel,
            user,
            origin_location=origin_locations.get(travel.origin_location_id),
            destination_location=dest_locations.get(travel.destination_location_id),
            emission=emissions.get(travel.id) if travel.id else None,
        )

    async def _fetch_related_data(
        self, travels: List[ProfessionalTravel]
    ) -> Tuple[
        dict[int, Location], dict[int, Location], dict[int, ProfessionalTravelEmission]
    ]:
        """
        Fetch related locations and emissions for a list of travels in bulk.

        Args:
            travels: List of professional travel records

        Returns:
            Tuple of (origin_locations dict, dest_locations dict, emissions dict)
            Each dict maps location_id or travel_id to the related object
        """
        if not travels:
            return {}, {}, {}

        # Collect all unique location IDs and travel IDs
        location_ids = set()
        travel_ids = []
        for travel in travels:
            if travel.id:
                travel_ids.append(travel.id)
            location_ids.add(travel.origin_location_id)
            location_ids.add(travel.destination_location_id)

        # Fetch all locations in one query
        all_locations = {}
        if location_ids:
            locations_stmt = select(Location).where(col(Location.id).in_(location_ids))
            locations_result = await self.session.execute(locations_stmt)
            all_locations = {loc.id: loc for loc in locations_result.scalars().all()}

        # Fetch all current emissions in one query
        emissions = {}
        if travel_ids:
            emissions_stmt = select(ProfessionalTravelEmission).where(
                and_(
                    col(ProfessionalTravelEmission.professional_travel_id).in_(
                        travel_ids
                    ),
                    col(ProfessionalTravelEmission.is_current) == True,  # noqa: E712
                )
            )
            emissions_result = await self.session.execute(emissions_stmt)
            emissions = {
                em.professional_travel_id: em for em in emissions_result.scalars().all()
            }

        # Build origin and destination location dicts
        origin_locations = {}
        dest_locations = {}
        for travel in travels:
            if travel.origin_location_id in all_locations:
                origin_locations[travel.origin_location_id] = all_locations[
                    travel.origin_location_id
                ]
            if travel.destination_location_id in all_locations:
                dest_locations[travel.destination_location_id] = all_locations[
                    travel.destination_location_id
                ]

        return origin_locations, dest_locations, emissions

    async def _batch_check_edit_permissions(
        self, travels: List[ProfessionalTravel], user: User
    ) -> dict[int, bool]:
        """
        Batch check edit permissions for multiple travel items in parallel.

        Args:
            travels: List of professional travel records
            user: Current user

        Returns:
            Dictionary mapping travel.id to can_edit boolean
        """
        if not travels:
            return {}

        # Build all permission check tasks in parallel
        tasks = []
        travel_ids = []
        for travel in travels:
            if travel.id is not None:
                tasks.append(can_user_edit_item(travel, user))
                travel_ids.append(travel.id)

        # Execute all permission checks in parallel
        results = await asyncio.gather(*tasks)

        # Map results back to travel IDs
        return dict(zip(travel_ids, results))

    async def _to_item_response(
        self,
        travel: ProfessionalTravel,
        user: User,
        origin_location: Optional[Location] = None,
        destination_location: Optional[Location] = None,
        emission: Optional[ProfessionalTravelEmission] = None,
        can_edit: Optional[bool] = None,
    ) -> ProfessionalTravelItemResponse:
        """
        Convert DB model to response DTO with can_edit flag.

        Args:
            travel: Professional travel record from database
            user: Current user
            origin_location: Optional origin location object
                (from locations table)
            destination_location: Optional destination location object
                (from locations table)
            emission: Optional emission object
                (from professional_travel_emissions table)
            can_edit: Optional pre-computed edit permission.
                If None, will be computed on-demand (slower for batches)

        Returns:
            ProfessionalTravelItemResponse with can_edit flag

        Raises:
            ValueError: If travel record has no ID
                (should never happen for saved records)
        """
        if travel.id is None:
            raise ValueError(
                "Cannot create response for travel record without ID. "
                "This should never happen for saved database records."
            )

        # Compute can_edit if not provided (for backward compatibility)
        if can_edit is None:
            can_edit = await can_user_edit_item(travel, user)

        # Type narrowing: travel.id is guaranteed to be int after the None check
        return ProfessionalTravelItemResponse(
            id=travel.id,
            traveler_name=travel.traveler_name,
            origin_location_id=travel.origin_location_id,
            destination_location_id=travel.destination_location_id,
            origin=origin_location.name if origin_location else None,
            destination=destination_location.name if destination_location else None,
            transport_mode=travel.transport_mode,
            class_=travel.class_,
            departure_date=travel.departure_date,
            number_of_trips=travel.number_of_trips,
            distance_km=emission.distance_km if emission else None,
            kg_co2eq=emission.kg_co2eq if emission else None,
            can_edit=can_edit,
        )

    async def _calculate_and_store_emission(
        self,
        travel_id: int,
        origin_location_id: int,
        destination_location_id: int,
        transport_mode: str,
        class_: Optional[str] = None,
        number_of_trips: int = 1,
    ) -> ProfessionalTravelEmission:
        """
        Calculate distance and CO2 emissions for a trip and store in emission table.

        Args:
            travel_id: Professional travel record ID
            origin_location_id: Origin location ID
            destination_location_id: Destination location ID
            transport_mode: 'flight' or 'train'
            class_: Travel class (optional)
            number_of_trips: Number of trips (default: 1)

        Returns:
            ProfessionalTravelEmission object

        Raises:
            HTTPException: If locations not found or calculation fails
        """
        # Fetch location objects
        origin_location = await self.session.get(Location, origin_location_id)
        if not origin_location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Origin location with ID {origin_location_id} not found",
            )

        dest_location = await self.session.get(Location, destination_location_id)
        if not dest_location:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Destination location with ID {destination_location_id} not found"
                ),
            )

        # Mark any existing current emission as not current
        existing_stmt = select(ProfessionalTravelEmission).where(
            ProfessionalTravelEmission.professional_travel_id == travel_id,
            ProfessionalTravelEmission.is_current,
        )
        existing_result = await self.session.execute(existing_stmt)
        existing_emissions = existing_result.scalars().all()
        for existing in existing_emissions:
            existing.is_current = False

        # Use TravelCalculationService to calculate emissions
        calculation_service = TravelCalculationService(self.session)

        if transport_mode == "flight":
            distance_km, kg_co2eq = await calculation_service.calculate_plane_emissions(
                origin_airport=origin_location,
                dest_airport=dest_location,
                class_=class_,
                number_of_trips=number_of_trips,
            )
            # TODO: Store plane_impact_factor_id when we have it
            plane_impact_factor_id = None
            train_impact_factor_id = None
        elif transport_mode == "train":
            distance_km, kg_co2eq = await calculation_service.calculate_train_emissions(
                origin_station=origin_location,
                dest_station=dest_location,
                class_=class_,
                number_of_trips=number_of_trips,
            )
            # TODO: Store train_impact_factor_id when we have it
            plane_impact_factor_id = None
            train_impact_factor_id = None
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Invalid transport_mode: {transport_mode}. "
                    "Must be 'flight' or 'train'"
                ),
            )

        # Create new emission record
        emission = ProfessionalTravelEmission(
            professional_travel_id=travel_id,
            distance_km=distance_km,
            kg_co2eq=kg_co2eq,
            plane_impact_factor_id=plane_impact_factor_id,
            train_impact_factor_id=train_impact_factor_id,
            formula_version="v1",
            calculation_inputs={
                "origin_location_id": origin_location_id,
                "destination_location_id": destination_location_id,
                "transport_mode": transport_mode,
                "class": class_,
                "number_of_trips": number_of_trips,
            },
            is_current=True,
        )

        self.session.add(emission)
        await self.session.commit()
        await self.session.refresh(emission)

        return emission

    async def get_module_data(
        self,
        unit_id: int,
        year: int,
        user: User,
        preview_limit: Optional[int] = None,
    ) -> ModuleResponse:
        """
        Get complete module data with summary stats and preview items.

        Args:
            unit_id: Unit identifier
            year: Year for filtering
            user: Current user (for filtering standard users)
            preview_limit: Optional limit for items per submodule

        Returns:
            ModuleResponse with totals + items
        """
        logger.info(
            f"Fetching module data for unit={sanitize(unit_id)}, "
            f"year={sanitize(year)}, module=professional-travel"
        )

        # Get summary statistics
        stats = await self.repo.get_summary_stats(unit_id=unit_id, year=year, user=user)

        # Get preview items (limited)
        limit = preview_limit or 10
        items, _ = await self.repo.get_travels(
            unit_id=unit_id,
            year=year,
            user=user,
            limit=limit,
            offset=0,
            sort_by="id",
            sort_order="desc",
            filter=None,
        )

        # Fetch related data (locations and emissions) in bulk
        origin_locations, dest_locations, emissions = await self._fetch_related_data(
            items
        )

        # Batch check edit permissions for all items in parallel
        can_edit_map = await self._batch_check_edit_permissions(items, user)

        # Convert to item responses with pre-computed can_edit flags
        item_responses = []
        for travel in items:
            item_response = await self._to_item_response(
                travel,
                user,
                origin_location=origin_locations.get(travel.origin_location_id),
                destination_location=dest_locations.get(travel.destination_location_id),
                emission=emissions.get(travel.id) if travel.id else None,
                can_edit=can_edit_map.get(travel.id) if travel.id else False,
            )
            item_responses.append(item_response)

        # Create submodule summary
        # (professional travel has no submodules, use single 'trips' key
        # to match frontend)
        summary = SubmoduleSummary(
            total_items=stats["total_items"],
            annual_fte=None,
            annual_consumption_kwh=None,
            total_kg_co2eq=stats["total_kg_co2eq"],
        )

        # Create submodule response
        submodule_response = SubmoduleResponse(
            id="trips",
            count=stats["total_items"],
            summary=summary,
            items=item_responses,
            has_more=stats["total_items"] > limit,
            name="Professional Travel",
        )

        # Calculate module totals
        totals = ModuleTotals(
            total_submodules=1,
            total_items=stats["total_items"],
            total_annual_fte=None,
            total_kg_co2eq=stats["total_kg_co2eq"],
            total_tonnes_co2eq=(
                round(stats["total_kg_co2eq"] / 1000, 2)
                if stats["total_kg_co2eq"]
                else None
            ),
            total_annual_consumption_kwh=None,
        )

        # Create module response
        module_response = ModuleResponse(
            module_type="professional-travel",
            unit="kg CO2eq",
            unit_id=unit_id,
            year=year,
            stats=None,
            retrieved_at=datetime.now(timezone.utc),
            submodules={"trips": submodule_response},
            totals=totals,
        )

        logger.info(
            f"Module data retrieved: {sanitize(stats['total_items'])} items, "
            f"{sanitize(stats['total_kg_co2eq'])} kg CO2eq"
        )

        return module_response

    async def get_submodule_data(
        self,
        unit_id: int,
        year: int,
        user: User,
        page: int = 1,
        limit: int = 100,
        sort_by: str = "id",
        sort_order: str = "desc",
        filter: Optional[str] = None,
    ) -> SubmoduleResponse:
        """
        Get submodule data with full pagination.

        Args:
            unit_id: Unit identifier
            year: Year for filtering
            user: Current user (for filtering standard users)
            page: Page number (1-based)
            limit: Items per page
            sort_by: Column to sort by
            sort_order: 'asc' or 'desc'
            filter: Optional text search filter

        Returns:
            SubmoduleResponse with items + pagination metadata
        """
        offset = (page - 1) * limit

        # Get travels with pagination
        items, total_count = await self.repo.get_travels(
            unit_id=unit_id,
            year=year,
            user=user,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            sort_order=sort_order,
            filter=filter,
        )

        # Fetch related data (locations and emissions) in bulk
        origin_locations, dest_locations, emissions = await self._fetch_related_data(
            items
        )

        # Batch check edit permissions for all items in parallel
        can_edit_map = await self._batch_check_edit_permissions(items, user)

        # Convert to item responses with pre-computed can_edit flags
        item_responses = []
        for travel in items:
            item_response = await self._to_item_response(
                travel,
                user,
                origin_location=origin_locations.get(travel.origin_location_id),
                destination_location=dest_locations.get(travel.destination_location_id),
                emission=emissions.get(travel.id) if travel.id else None,
                can_edit=can_edit_map.get(travel.id) if travel.id else False,
            )
            item_responses.append(item_response)

        # Get summary stats for this query
        stats = await self.repo.get_summary_stats(unit_id=unit_id, year=year, user=user)

        summary = SubmoduleSummary(
            total_items=total_count,
            annual_fte=None,
            annual_consumption_kwh=None,
            total_kg_co2eq=stats["total_kg_co2eq"],
        )

        # Create submodule response
        submodule_response = SubmoduleResponse(
            id="trips",
            count=total_count,
            summary=summary,
            items=item_responses,
            has_more=offset + limit < total_count,
            name="Professional Travel",
        )

        return submodule_response

    async def get_module_stats(
        self, unit_id: int, year: int, user: User
    ) -> dict[str, float]:
        """
        Get aggregated summary statistics for professional travels.

        Args:
            unit_id: Unit identifier
            year: Year filter
            user: Current user (for filtering standard users)

        Returns:
            Dict with total_items, total_kg_co2eq, total_distance_km
        """
        return await self.repo.get_summary_stats(unit_id=unit_id, year=year, user=user)

    async def get_stats_by_class(
        self, unit_id: int, year: int, user: User
    ) -> List[dict[str, Any]]:
        """
        Get professional travel statistics aggregated by transport mode and class.

        Args:
            unit_id: Unit identifier
            year: Year filter
            user: Current user (for filtering standard users)

        Returns:
            List of dicts in treemap format with hierarchical structure:
            Each dict has "name" (category), "value" (total kg_co2eq), and "children"
            array with class-level data including "name", "value", and "percentage"
        """
        return await self.repo.get_stats_by_class(unit_id=unit_id, year=year, user=user)

    async def get_evolution_over_time(
        self, unit_id: int, user: User
    ) -> List[dict[str, Any]]:
        """
        Get professional travel statistics aggregated by year and transport mode.

        Args:
            unit_id: Unit identifier
            user: Current user (for filtering standard users)

        Returns:
            List of dicts with year, transport_mode, and kg_co2eq:
            [
                {"year": 2020, "transport_mode": "flight", "kg_co2eq": 15000.0},
                {"year": 2020, "transport_mode": "train", "kg_co2eq": 8000.0},
                ...
            ]
        """
        return await self.repo.get_evolution_over_time(unit_id=unit_id, user=user)

    async def create_travel(
        self,
        data: ProfessionalTravelCreate,
        provider_source: str,
        user: User,
        year: Optional[int] = None,
        unit_id: Optional[int] = None,
    ) -> Union[ProfessionalTravel, List[ProfessionalTravel]]:
        """
        Create a new professional travel record.

        Args:
            data: Travel creation data
            provider_source: Provider source ('manual', 'api', 'csv')
            user: Current user
            year: Optional year from workspace setup. Used when departure_date is empty.
            unit_id: Optional unit_id from path. Validated against data.unit_id if
                provided.

        Returns:
            Created ProfessionalTravel record(s) - list if round trip

        Raises:
            HTTPException: 422 if traveler validation fails
        """
        # Look up traveler_id from traveler_name if not provided,
        # or validate if provided
        traveler_id = user.id
        if traveler_id is None:
            logger.warning(
                f"Traveler validation failed: "
                f"traveler_name={sanitize(data.traveler_name)}, "
                f"unit_id={sanitize(data.unit_id)}"
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Traveler '{data.traveler_name}' not found in headcount "
                    f"for unit ID {data.unit_id}"
                ),
            )
        data.traveler_id = traveler_id

        logger.info(
            f"Creating travel record: unit={sanitize(data.unit_id)}, "
            f"traveler_id={sanitize(traveler_id)}, "
            f"traveler_name={sanitize(data.traveler_name)}, "
            f"origin_location_id={data.origin_location_id}, "
            f"destination_location_id={data.destination_location_id}, "
            f"provider={sanitize(provider_source)}, "
            f"year={year}"
        )

        if user is None or user.id is None:
            logger.error("User context is required for creating travel")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User context is required for creating travel",
            )
        # Create travel record(s) via repository
        travel_records = await self.repo.create_travel(
            data=data,
            provider_source=provider_source,
            user_id=user.id,
            year=year,
            unit_id=unit_id,
        )

        # Calculate and store emissions (skip for API trips)
        if provider_source != "api":
            # Handle both single record and list (round trip)
            records_to_process = (
                travel_records if isinstance(travel_records, list) else [travel_records]
            )

            for travel_record in records_to_process:
                if travel_record.id is None:
                    logger.error(f"Travel record created without ID: {travel_record}")
                    continue

                await self._calculate_and_store_emission(
                    travel_id=travel_record.id,
                    origin_location_id=travel_record.origin_location_id,
                    destination_location_id=travel_record.destination_location_id,
                    transport_mode=travel_record.transport_mode,
                    class_=travel_record.class_,
                    number_of_trips=travel_record.number_of_trips,
                )

        records_for_log = (
            records_to_process if isinstance(travel_records, list) else [travel_records]
        )
        logger.info(
            f"Travel record(s) created: id(s)={[r.id for r in records_for_log]}"
        )

        return travel_records

    async def update_travel(
        self,
        travel_id: int,
        data: ProfessionalTravelUpdate,
        user: User,
    ) -> Optional[ProfessionalTravel]:
        """
        Update an existing professional travel record.

        Args:
            travel_id: Travel record identifier
            data: Partial update data
            user: Current user

        Returns:
            Updated ProfessionalTravel if found and authorized

        Raises:
            HTTPException: 403 if permission denied, 404 if not found
        """
        logger.info(
            f"Updating travel record: id={sanitize(travel_id)}, "
            f"user={sanitize(user.id)}"
        )

        # Fetch record with user filtering
        travel = await self.repo.get_by_id(travel_id, user)
        if not travel:
            logger.warning(
                f"Travel record not found: id={sanitize(travel_id)}, "
                f"user={sanitize(user.id)}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Travel record with ID {travel_id} not found",
            )

        # Check permission using OPA resource access policy
        if not await can_user_edit_item(travel, user):
            logger.warning(
                f"Permission denied for travel update: id={sanitize(travel_id)}, "
                f"user={sanitize(user.id)}, provider={sanitize(travel.provider)}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to edit this travel record",
            )

        # Validate traveler if changed
        update_data = data.model_dump(exclude_unset=True)
        traveler_id = update_data.get("traveler_id", travel.traveler_id)
        unit_id = update_data.get("unit_id", travel.unit_id)

        if "traveler_id" in update_data:
            await self._validate_traveler(traveler_id, travel.traveler_name, unit_id)

        # Determine if recalculation is needed
        needs_recalculation = any(
            field in update_data
            for field in [
                "origin_location_id",
                "destination_location_id",
                "transport_mode",
                "class_",
                "number_of_trips",
            ]
        )
        if not user or not user.id:
            logger.error("User context is required for updating travel")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="User context is required for updating travel",
            )
        # Update travel record via repository
        updated = await self.repo.update_travel(
            travel_id=travel_id, data=data, user_id=user.id, user=user
        )

        # Recalculate and store emissions if needed (and not API trip)
        if needs_recalculation and travel.provider != "api" and updated:
            if updated.id is None:
                logger.error(
                    f"Travel record updated without ID: id={sanitize(travel_id)}"
                )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Travel record updated without ID",
                )
            await self._calculate_and_store_emission(
                travel_id=updated.id,
                origin_location_id=updated.origin_location_id,
                destination_location_id=updated.destination_location_id,
                transport_mode=updated.transport_mode,
                class_=updated.class_,
                number_of_trips=updated.number_of_trips,
            )

        logger.info(f"Travel record updated: id={sanitize(travel_id)}")

        return updated

    async def delete_travel(self, travel_id: int, user: User) -> bool:
        """
        Delete a professional travel record.

        Args:
            travel_id: Travel record identifier
            user: Current user

        Returns:
            True if deleted successfully

        Raises:
            HTTPException: 403 if permission denied, 404 if not found
        """
        logger.info(
            f"Deleting travel record: id={sanitize(travel_id)}, "
            f"user={sanitize(user.id)}"
        )

        # Fetch record with user filtering
        travel = await self.repo.get_by_id(travel_id, user)
        if not travel:
            logger.warning(
                f"Travel record not found for deletion: id={sanitize(travel_id)}, "
                f"user={sanitize(user.id)}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Travel record with ID {travel_id} not found",
            )

        # Check permission using OPA resource access policy
        if not await can_user_edit_item(travel, user):
            logger.warning(
                f"Permission denied for travel deletion: id={sanitize(travel_id)}, "
                f"user={sanitize(user.id)}, provider={sanitize(travel.provider)}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this travel record",
            )

        # Delete travel record via repository
        success = await self.repo.delete_travel(travel_id, user)

        logger.info(
            f"Travel record deleted: id={sanitize(travel_id)}, "
            f"success={sanitize(success)}"
        )

        return success
