"""Professional Travel repository for database operations."""

from datetime import datetime, timezone
from typing import Any, List, Optional, Tuple, Union

from sqlalchemy import and_, func, or_
from sqlalchemy.sql import Select
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import _sanitize_for_log as sanitize
from app.core.logging import get_logger
from app.models.location import Location
from app.models.professional_travel import (
    ProfessionalTravel,
    ProfessionalTravelCreate,
    ProfessionalTravelEmission,
    ProfessionalTravelUpdate,
)
from app.models.user import RoleName, User

logger = get_logger(__name__)


class ProfessionalTravelRepository:
    """Repository for ProfessionalTravel database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    def _is_standard_user(self, user: User) -> bool:
        """Check if user has standard user role (co2.user.std)."""
        return user.has_role(RoleName.CO2_USER_STD.value)

    async def get_travels(
        self,
        unit_id: str,
        year: int,
        user: User,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
        filter: Optional[str] = None,
        filters: Optional[dict] = None,
    ) -> Tuple[List[ProfessionalTravel], int]:
        """
        Get professional travel records by unit_id and year.

        Args:
            unit_id: Unit identifier
            year: Year filter
            user: Current user (for filtering standard users)
            limit: Maximum number of records to return
            offset: Number of records to skip
            sort_by: Column name to sort by
            sort_order: 'asc' or 'desc'
            filter: Optional text search filter
            filters: Optional dict with additional filters (unit_id, user_id, etc.)

        Returns:
            Tuple of (list of ProfessionalTravel records, total count)
        """
        # Field mapping for sortable columns (including joined tables)
        # Use aliases for locations since we need two separate joins
        origin_location = Location.__table__.alias("origin_location")  # type: ignore[attr-defined]
        dest_location = Location.__table__.alias("dest_location")  # type: ignore[attr-defined]

        # For direct columns, use getattr like headcount does
        # For joined columns, use col() with the alias
        field_mapping: dict[str, Any] = {
            "id": getattr(ProfessionalTravel, "id"),
            "traveler_name": getattr(ProfessionalTravel, "traveler_name"),
            "transport_mode": getattr(ProfessionalTravel, "transport_mode"),
            "class": getattr(ProfessionalTravel, "class_"),
            "number_of_trips": getattr(ProfessionalTravel, "number_of_trips"),
            "departure_date": getattr(ProfessionalTravel, "departure_date"),
            "is_round_trip": getattr(ProfessionalTravel, "is_round_trip"),
            "unit_id": getattr(ProfessionalTravel, "unit_id"),
            "created_at": getattr(ProfessionalTravel, "created_at"),
            "updated_at": getattr(ProfessionalTravel, "updated_at"),
            "origin": col(origin_location.c.name),
            "destination": col(dest_location.c.name),
        }

        # Base query - always join with locations and emissions for sorting
        statement = (
            select(ProfessionalTravel)
            .outerjoin(
                origin_location,
                col(origin_location.c.id) == col(ProfessionalTravel.origin_location_id),
            )
            .outerjoin(
                dest_location,
                col(dest_location.c.id)
                == col(ProfessionalTravel.destination_location_id),
            )
            .outerjoin(
                ProfessionalTravelEmission,
                and_(
                    col(ProfessionalTravelEmission.professional_travel_id)
                    == col(ProfessionalTravel.id),
                    col(ProfessionalTravelEmission.is_current) == True,  # noqa: E712
                ),
            )
            .where(
                ProfessionalTravel.year == year,
            )
        )

        # Apply filters from filters dict
        if filters:
            # Apply unit_ids filter (list of unit IDs)
            if "unit_ids" in filters:
                statement = statement.where(
                    col(ProfessionalTravel.unit_id).in_(filters["unit_ids"])
                )
            # Apply user_id filter (filter by creator)
            if "user_id" in filters:
                statement = statement.where(
                    ProfessionalTravel.created_by == filters["user_id"]
                )

        # Legacy unit_id parameter (only apply if no filters provided)
        if not filters or "unit_ids" not in filters:
            if unit_id:
                statement = statement.where(ProfessionalTravel.unit_id == unit_id)

        # Add emission fields to field mapping
        field_mapping["distance_km"] = col(ProfessionalTravelEmission.distance_km)
        field_mapping["kg_co2eq"] = col(ProfessionalTravelEmission.kg_co2eq)

        # User filter for standard users: only see own records
        if self._is_standard_user(user):
            logger.info(
                f"[professional_travel_repo] Filtering travels for standard user: "
                f"user_id={user.id}, year={year}"
            )
            statement = statement.where(ProfessionalTravel.created_by == user.id)

        # Text search filter
        if filter:
            filter = filter.strip()
            # Max filter length for security
            if len(filter) > 100:
                filter = filter[:100]
            # Check for empty or only-wildcard filters
            if filter and filter not in ("", "%", "*"):
                filter_pattern = f"%{filter}%"
                statement = statement.where(
                    or_(
                        col(ProfessionalTravel.traveler_name).ilike(filter_pattern),
                        col(origin_location.c.name).ilike(filter_pattern),
                        col(dest_location.c.name).ilike(filter_pattern),
                    )
                )

        # Sorting using field mapping
        if sort_by in field_mapping:
            sort_column = field_mapping[sort_by]
            logger.debug(f"Sorting by {sort_by} using column: {sort_column}")
        else:
            # Fallback to ID if field not found
            logger.warning(
                f"Sort field '{sort_by}' not found in field_mapping, "
                f"falling back to 'id'"
            )
            sort_column = field_mapping["id"]

        if sort_order.lower() == "asc":
            statement = statement.order_by(sort_column.asc())
        else:
            statement = statement.order_by(sort_column.desc())

        # Pagination
        statement = statement.offset(offset).limit(limit)

        # Execute query
        result = await self.session.execute(statement)
        items = list(result.scalars().all())

        # Count query for total - use subquery to match main query structure
        count_origin = Location.__table__.alias("count_origin")  # type: ignore[attr-defined]
        count_dest = Location.__table__.alias("count_dest")  # type: ignore[attr-defined]

        count_base = (
            select(ProfessionalTravel.id)
            .outerjoin(
                count_origin,
                col(count_origin.c.id) == col(ProfessionalTravel.origin_location_id),
            )
            .outerjoin(
                count_dest,
                col(count_dest.c.id) == col(ProfessionalTravel.destination_location_id),
            )
            .where(
                ProfessionalTravel.year == year,
            )
        )

        # Apply filters from filters dict (same as main query)
        if filters:
            # Apply unit_ids filter (list of unit IDs)
            if "unit_ids" in filters:
                count_base = count_base.where(
                    col(ProfessionalTravel.unit_id).in_(filters["unit_ids"])
                )
            # Apply user_id filter (filter by creator)
            if "user_id" in filters:
                count_base = count_base.where(
                    ProfessionalTravel.created_by == filters["user_id"]
                )

        # Legacy unit_id parameter (only apply if no filters provided)
        if not filters or "unit_ids" not in filters:
            if unit_id:
                count_base = count_base.where(ProfessionalTravel.unit_id == unit_id)

        # Apply same user filter for standard users
        if self._is_standard_user(user):
            count_base = count_base.where(ProfessionalTravel.created_by == user.id)

        # Apply same text search filter
        if filter and filter not in ("", "%", "*"):
            filter_pattern = f"%{filter}%"
            count_base = count_base.where(
                or_(
                    col(ProfessionalTravel.traveler_name).ilike(filter_pattern),
                    col(count_origin.c.name).ilike(filter_pattern),
                    col(count_dest.c.name).ilike(filter_pattern),
                )
            )

        count_stmt = select(func.count()).select_from(count_base.subquery())
        total_count = (await self.session.execute(count_stmt)).scalar_one()

        return items, total_count

    async def get_by_id(
        self, travel_id: int, user: User
    ) -> Optional[ProfessionalTravel]:
        """
        Get a single professional travel record by ID.

        Args:
            travel_id: Travel record identifier
            user: Current user (for filtering standard users)

        Returns:
            Optional[ProfessionalTravel] if found and accessible, None otherwise
        """
        statement = select(ProfessionalTravel).where(ProfessionalTravel.id == travel_id)

        # User filter for standard users: only see own records
        if self._is_standard_user(user):
            statement = statement.where(ProfessionalTravel.created_by == user.id)

        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def bulk_insert_travel_entries(
        self, entries: List[dict[str, Any]]
    ) -> List[ProfessionalTravel]:
        """
        Bulk insert professional travel entries.

        Args:
            entries: List of dicts representing professional travel data

        Returns:
            List of ProfessionalTravel instances that were inserted
        """
        db_objs = [ProfessionalTravel.model_validate(entry) for entry in entries]
        self.session.add_all(db_objs)
        await self.session.commit()
        for obj in db_objs:
            await self.session.refresh(obj)
        return db_objs

    async def create_travel(
        self,
        data: ProfessionalTravelCreate,
        provider_source: str,
        user_id: str,
        year: Optional[int] = None,
        unit_id: Optional[str] = None,
    ) -> Union[ProfessionalTravel, List[ProfessionalTravel]]:
        """
        Create a new professional travel record.

        If is_round_trip is True, creates 2 records (outbound and return).

        Args:
            data: Travel data to create
            provider_source: Provider source ('manual', 'api', 'csv')
            user_id: User ID who created the record
            year: Optional year from workspace setup. Used when departure_date is empty.
            unit_id: Optional unit_id from path. Validated against data.unit_id if
                provided.

        Returns:
            ProfessionalTravel or List[ProfessionalTravel] if round trip
        """
        # Validate unit_id matches if provided
        if unit_id is not None and data.unit_id != unit_id:
            raise ValueError(
                f"unit_id in path ({unit_id}) must match unit_id in data "
                f"({data.unit_id})"
            )

        # Calculate year from departure_date
        if data.departure_date:
            year = data.departure_date.year
            logger.info(
                f"[professional_travel_repo] Using year from departure_date: {year}"
            )
        elif year is not None:
            # Use provided year from workspace setup if no departure_date
            logger.info(
                f"[professional_travel_repo] Using year from workspace setup: {year}"
            )
        else:
            # Fallback to current year if no departure_date and no year provided
            year = datetime.now(timezone.utc).year
            logger.info(
                f"[professional_travel_repo] Using current year as fallback: {year}"
            )

        # Log user_id for debugging
        logger.info(
            f"[professional_travel_repo] Creating travel with user_id={user_id}, "
            f"unit_id={data.unit_id}, traveler_name={data.traveler_name}, "
            f"is_round_trip={data.is_round_trip}, year={year}, "
            f"departure_date={data.departure_date}"
        )

        # Handle round trip: create 2 records
        if data.is_round_trip:
            # Outbound trip
            outbound_data = data.model_dump()
            outbound_data["year"] = year
            outbound_data["provider"] = provider_source
            outbound_data["created_by"] = user_id
            outbound_data["updated_by"] = user_id
            outbound_data["is_round_trip"] = False

            outbound = ProfessionalTravel.model_validate(outbound_data)
            self.session.add(outbound)

            # Return trip (swap origin and destination)
            return_data = data.model_dump()
            return_data["origin_location_id"] = data.destination_location_id
            return_data["destination_location_id"] = data.origin_location_id
            # Use same departure_date for return trip (or None if not provided)
            return_data["departure_date"] = data.departure_date
            return_data["year"] = (
                data.departure_date.year if data.departure_date else year
            )
            return_data["provider"] = provider_source
            return_data["created_by"] = user_id
            return_data["updated_by"] = user_id
            return_data["is_round_trip"] = False

            return_trip = ProfessionalTravel.model_validate(return_data)
            self.session.add(return_trip)

            await self.session.commit()
            await self.session.refresh(outbound)
            await self.session.refresh(return_trip)

            return [outbound, return_trip]
        else:
            # Single trip
            db_obj = ProfessionalTravel.model_validate(
                {**data.model_dump(), "year": year}
            )
            db_obj.provider = provider_source
            db_obj.created_by = user_id
            db_obj.updated_by = user_id

            self.session.add(db_obj)
            await self.session.commit()
            await self.session.refresh(db_obj)

            return db_obj

    async def update_travel(
        self, travel_id: int, data: ProfessionalTravelUpdate, user_id: str, user: User
    ) -> Optional[ProfessionalTravel]:
        """
        Update an existing professional travel record.

        Args:
            travel_id: Travel record identifier
            data: Partial update data
            user_id: User ID who updated the record
            user: Current user (for permission checking)

        Returns:
            Optional[ProfessionalTravel] if found and updated, None otherwise
        """
        # Fetch the existing record with user filtering
        statement = select(ProfessionalTravel).where(ProfessionalTravel.id == travel_id)

        # User filter for standard users: only update own records
        if self._is_standard_user(user):
            statement = statement.where(ProfessionalTravel.created_by == user.id)

        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return None

        # Update fields from input model (only provided fields)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        # Recalculate year if departure_date changed
        if "departure_date" in update_data and db_obj.departure_date:
            db_obj.year = db_obj.departure_date.year

        # Set system-determined fields
        db_obj.updated_by = user_id
        db_obj.updated_at = datetime.now(timezone.utc)

        # Save
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)

        return db_obj

    async def delete_travel(self, travel_id: int, user: User) -> bool:
        """
        Delete a professional travel record and all related emissions.

        Args:
            travel_id: Travel record identifier
            user: Current user (for permission checking)

        Returns:
            bool: True if deleted successfully, False if not found
        """
        from sqlmodel import delete as sqlmodel_delete

        # Fetch the existing record with user filtering
        statement = select(ProfessionalTravel).where(ProfessionalTravel.id == travel_id)

        # User filter for standard users: only delete own records
        if self._is_standard_user(user):
            statement = statement.where(ProfessionalTravel.created_by == user.id)

        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return False

        # First, delete all related emissions
        delete_emissions_stmt = sqlmodel_delete(ProfessionalTravelEmission).where(
            col(ProfessionalTravelEmission.professional_travel_id) == travel_id
        )
        await self.session.execute(delete_emissions_stmt)

        # Then delete the travel record
        await self.session.delete(db_obj)
        await self.session.commit()

        logger.info(
            f"Deleted professional travel {travel_id} and its related emissions"
        )

        return True

    async def get_summary_stats(self, unit_id: str, year: int, user: User) -> dict:
        """
        Get aggregated summary statistics for professional travels.

        Args:
            unit_id: Unit identifier
            year: Year filter
            user: Current user (for filtering standard users)

        Returns:
            Dict with total_items, total_kg_co2eq, total_distance_km
        """
        # Build aggregation query - join with emissions table
        query = (
            select(
                func.count(col(ProfessionalTravel.id)).label("total_items"),
                func.sum(col(ProfessionalTravelEmission.kg_co2eq)).label(
                    "total_kg_co2eq"
                ),
                func.sum(col(ProfessionalTravelEmission.distance_km)).label(
                    "total_distance_km"
                ),
            )
            .join(
                ProfessionalTravelEmission,
                and_(
                    col(ProfessionalTravelEmission.professional_travel_id)
                    == col(ProfessionalTravel.id),
                    col(ProfessionalTravelEmission.is_current) == True,  # noqa: E712
                ),
                isouter=True,  # LEFT JOIN to include travels without emissions
            )
            .where(
                ProfessionalTravel.unit_id == unit_id,
                ProfessionalTravel.year == year,
            )
        )

        # Apply user filter for standard users
        if self._is_standard_user(user):
            query = query.where(ProfessionalTravel.created_by == user.id)

        # Execute query
        result = await self.session.execute(query)
        row = result.one()

        return {
            "total_items": int(row.total_items or 0),
            "total_kg_co2eq": float(row.total_kg_co2eq or 0.0),
            "total_distance_km": float(row.total_distance_km or 0.0),
        }

    async def get_stats_by_class(
        self, unit_id: str, year: int, user: User
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
        # Build aggregation query grouped by transport_mode and class
        # Only include rows with actual emissions (INNER JOIN)
        query: Select = (
            select(
                col(ProfessionalTravel.transport_mode).label("category"),
                col(ProfessionalTravel.class_).label("class_key"),
                func.sum(col(ProfessionalTravelEmission.kg_co2eq)).label("kg_co2eq"),
            )
            .join(
                ProfessionalTravelEmission,
                and_(
                    col(ProfessionalTravelEmission.professional_travel_id)
                    == col(ProfessionalTravel.id),
                    col(ProfessionalTravelEmission.is_current) == True,  # noqa: E712
                ),
            )
            .where(
                ProfessionalTravel.unit_id == unit_id,
                ProfessionalTravel.year == year,
                col(ProfessionalTravelEmission.kg_co2eq).isnot(None),
                col(ProfessionalTravelEmission.kg_co2eq) > 0,
            )
            .group_by(
                col(ProfessionalTravel.transport_mode),
                col(ProfessionalTravel.class_),
            )
        )

        # Apply user filter for standard users
        if self._is_standard_user(user):
            query = query.where(col(ProfessionalTravel.created_by) == user.id)

        # Execute query
        result = await self.session.execute(query)
        rows = result.all()

        logger.info(
            f"get_stats_by_class: Found {len(rows)} rows for "
            f"unit_id={sanitize(unit_id)}, year={year}"
        )

        # Group by category (transport_mode) and aggregate by class
        data_dict: dict[str, dict[str, float]] = {}
        for row in rows:
            category = row.category or "unknown"
            class_key = row.class_key
            kg_co2eq = float(row.kg_co2eq or 0.0)

            # Skip rows with zero or null emissions
            if kg_co2eq <= 0:
                logger.debug(
                    f"Skipping row with zero emissions: category={category}, "
                    f"class={class_key}"
                )
                continue

            if category not in data_dict:
                data_dict[category] = {}

            # Handle null class_key - use a default based on category
            if class_key is None:
                # Default class for flights/trains without class specified
                if category == "flight":
                    class_key = "eco"  # Default to eco for flights
                elif category == "train":
                    class_key = "class_2"  # Default to class_2 for trains
                else:
                    class_key = "unknown"
                logger.debug(
                    f"Using default class '{class_key}' for category '{category}' "
                    f"with null class"
                )

            # Sum emissions by class (handle multiple rows with same class)
            data_dict[category][class_key] = (
                data_dict[category].get(class_key, 0.0) + kg_co2eq
            )

        # Calculate total kg_co2eq across all categories and classes
        total_kg_co2eq = sum(sum(classes.values()) for classes in data_dict.values())

        # Convert to treemap format: hierarchical structure with name,
        # value, and children
        result_list = []
        for category, classes in data_dict.items():
            category_total = sum(classes.values())

            # Build children array for this category
            children = []
            for class_key, kg_co2eq in classes.items():
                class_percentage = (
                    (kg_co2eq / total_kg_co2eq * 100) if total_kg_co2eq > 0 else 0.0
                )
                children.append(
                    {
                        "name": class_key,
                        "value": kg_co2eq,
                        "percentage": class_percentage,
                    }
                )

            # Only include categories with valid children
            if children and category_total > 0:
                result_list.append(
                    {
                        "name": category,
                        "value": category_total,
                        "children": children,
                    }
                )
                logger.info(
                    f"Category '{category}' with classes: {list(classes.keys())}, "
                    f"total items: {len(result_list)}"
                )

        logger.info(f"get_stats_by_class: Returning {len(result_list)} categories")
        return result_list

    async def get_evolution_over_time(
        self, unit_id: str, user: User
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
        # Build aggregation query grouped by year and transport_mode
        # Only include rows with actual emissions (INNER JOIN)
        query: Select = (
            select(
                col(ProfessionalTravel.year).label("year"),
                col(ProfessionalTravel.transport_mode).label("transport_mode"),
                func.sum(col(ProfessionalTravelEmission.kg_co2eq)).label("kg_co2eq"),
            )
            .join(
                ProfessionalTravelEmission,
                and_(
                    col(ProfessionalTravelEmission.professional_travel_id)
                    == col(ProfessionalTravel.id),
                    col(ProfessionalTravelEmission.is_current) == True,  # noqa: E712
                ),
            )
            .where(
                ProfessionalTravel.unit_id == unit_id,
                col(ProfessionalTravelEmission.kg_co2eq).isnot(None),
                col(ProfessionalTravelEmission.kg_co2eq) > 0,
            )
            .group_by(
                col(ProfessionalTravel.year),
                col(ProfessionalTravel.transport_mode),
            )
            .order_by(
                col(ProfessionalTravel.year).asc(),
                col(ProfessionalTravel.transport_mode).asc(),
            )
        )

        # Apply user filter for standard users
        if self._is_standard_user(user):
            query = query.where(col(ProfessionalTravel.created_by) == user.id)

        # Execute query
        result = await self.session.execute(query)
        rows = result.all()

        logger.info(
            f"get_evolution_over_time: Found {len(rows)} rows for "
            f"unit_id={sanitize(unit_id)}"
        )

        # Convert to list of dicts
        result_list = []
        for row in rows:
            result_list.append(
                {
                    "year": int(row.year),
                    "transport_mode": row.transport_mode or "unknown",
                    "kg_co2eq": float(row.kg_co2eq or 0.0),
                }
            )

        logger.info(f"get_evolution_over_time: Returning {len(result_list)} rows")
        return result_list
