"""Headcount repository for database operations."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.headcount import HeadCount, HeadCountCreate, HeadCountUpdate
from app.schemas.equipment import SubmoduleResponse, SubmoduleSummary

logger = get_logger(__name__)


# Mapping from French HR roles to broad English categories (snake_case)
ROLE_CATEGORY_MAPPING = {
    # Professor roles
    "Professeur titulaire": "professor",
    "Professeur": "professor",
    "Maître d'enseignement et de recherche": "professor",
    # Scientific Collaborator roles
    "Collaborateur scientifique": "scientific_collaborator",
    "Collaborateur scientifique senior": "scientific_collaborator",
    "Informaticien": "scientific_collaborator",
    "Adjoint scientifique": "scientific_collaborator",
    "Assistant scientifique": "scientific_collaborator",
    # Student roles
    "Étudiant-e": "student",
    "Étudiant en échange": "student",
    "Stagiaire étudiant": "student",
    "Student": "student",  # English variant
    # Postdoctoral Researcher
    "Post-Doctorant": "postdoctoral_researcher",
    # Doctoral Assistant
    "Assistant-doctorant": "doctoral_assistant",
    "Doctorant-e en échange": "doctoral_assistant",
    # Trainee roles
    "Apprenti": "trainee",
    "Apprenti Interactive Media Designer": "trainee",
    "Apprenti gardien d'animaux": "trainee",
    "Apprenti informaticien": "trainee",
    "Apprenti laborant en biologie": "trainee",
    "Stagiaire": "trainee",
    "Stagiare": "trainee",  # Typo variant
    # Technical / Administrative Staff
    "Assistant technique": "technical_administrative_staff",
    "Chef de l'animalerie": "technical_administrative_staff",
    "Chef du service technique": "technical_administrative_staff",
    "Chef laborant": "technical_administrative_staff",
    "Collaborateur administratif": "technical_administrative_staff",
    "Assistant-e administratif-ve": "technical_administrative_staff",
    "Secrétaire": "technical_administrative_staff",
    "Chargé-e de communication": "technical_administrative_staff",
    "Ingénieur": "technical_administrative_staff",
    "Collaborateur technique": "technical_administrative_staff",
    "Aide de Laboratoire": "technical_administrative_staff",
    "Ingénieur Système": "technical_administrative_staff",
    "Adjoint": "technical_administrative_staff",
    "Adjoint au Chef du Département": "technical_administrative_staff",
    "Adjoint de section": "technical_administrative_staff",
    "Team Leader": "technical_administrative_staff",
    "Responsable de la laverie": "technical_administrative_staff",
    "Responsable des infrastructures": "technical_administrative_staff",
    "Responsable informatique": "technical_administrative_staff",
    "Responsable magasin principal": "technical_administrative_staff",
    "Adjoint à la direction": "technical_administrative_staff",
    "Animalier": "technical_administrative_staff",
    "Assistant": "technical_administrative_staff",
    "Coordinateur": "technical_administrative_staff",
    "Electronicien": "technical_administrative_staff",
    "Ingénieur Chimiste": "technical_administrative_staff",
    "Journaliste": "technical_administrative_staff",
    "Laborant-e senior": "technical_administrative_staff",
    "Laborantin-e": "technical_administrative_staff",
    "Magasinier": "technical_administrative_staff",
    "Programmeur": "technical_administrative_staff",
    "Spécialiste communication": "technical_administrative_staff",
    "Spécialiste système": "technical_administrative_staff",
    "Spécialiste technique": "technical_administrative_staff",
    "Technicien": "technical_administrative_staff",
    # Other roles
    "Chargé-e de projet": "other",
    "Vétérinaire": "other",
    "Coordinateur-trice de Projets": "other",
    "RSE": "other",
    "Sciencepreneur": "other",
}


def get_function_role(function: str) -> str:
    """
    Get the English category for a French HR role.

    Args:
        french_role: The French HR role name

    Returns:
        The English category name (snake_case), or None if not found
    """
    return ROLE_CATEGORY_MAPPING.get(function, "other")


class HeadCountRepository:
    """Repository for HeadCount database operations."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_module_stats(
        self, unit_id: str, year: int, aggregate_by: str = "submodule"
    ) -> Dict[str, int]:
        """Aggregate headcount data by submodule or function."""
        group_field = getattr(HeadCount, aggregate_by)

        query = (
            select(group_field, func.count().label("total_count"))
            .where(
                HeadCount.unit_id == unit_id,
                # HeadCount.year == year,
            )
            .group_by(group_field)
        )

        result = await self.session.exec(query)
        rows = list(result.all())

        aggregation: Dict[str, int] = {}
        for key, total_count in rows:
            if key is None:
                aggregation["unknown"] = int(total_count)
            else:
                aggregation[key] = int(total_count)

        logger.debug(f"Aggregated headcount by {aggregate_by}: {aggregation}")

        return aggregation

    async def create_headcount(
        self, data: HeadCountCreate, provider_source: str, user_id: str
    ) -> HeadCount:
        """Create a new headcount record."""
        # 1. Convert Input Model to Table Model

        function_role = get_function_role(data.function or "")
        if data.submodule == "student" and function_role != "student":
            function_role = "student"
        db_obj = HeadCount.model_validate(
            {**data.dict(), "function_role": function_role}
        )

        # 2. Add System-Determined Fields
        db_obj.provider = provider_source  # e.g., "csv_upload"
        db_obj.created_by = user_id
        db_obj.updated_by = user_id

        # 3. Save
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def update_headcount(
        self, headcount_id: int, data: HeadCountUpdate, user_id: str
    ) -> Optional[HeadCount]:
        """Update an existing headcount record."""
        # 1. Fetch the existing record

        statement = select(HeadCount).where(HeadCount.id == headcount_id)
        result = await self.session.exec(statement)
        db_obj = result.one_or_none()

        if not db_obj:
            return None

        # 2. Update fields from input model (only provided fields)
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_obj, field, value)

        # add function_role update
        if "function" in update_data:
            function_role = get_function_role(update_data["function"])
            if db_obj.submodule == "student" and function_role != "student":
                function_role = "student"
            db_obj.function_role = function_role

        # 3. Add System-Determined Fields
        db_obj.updated_by = user_id
        db_obj.updated_at = datetime.now(timezone.utc)

        # 4. Save
        self.session.add(db_obj)
        await self.session.commit()
        await self.session.refresh(db_obj)
        return db_obj

    async def delete_headcount(self, headcount_id: int) -> bool:
        """Delete a headcount record."""
        # 1. Fetch the existing record
        statement = select(HeadCount).where(HeadCount.id == headcount_id)
        result = await self.session.execute(statement)
        db_obj = result.scalar_one_or_none()

        if not db_obj:
            return False

        # 2. Delete
        await self.session.delete(db_obj)
        await self.session.commit()
        return True

    async def get_headcounts(
        self,
        unit_id,
        year,
        limit,
        offset,
        sort_by,
        sort_order,
        filter: Optional[str] = None,
    ) -> list[HeadCount]:
        """Get headcount record by unit_id and year."""
        statement = select(HeadCount).where(
            HeadCount.unit_id == unit_id,
            # HeadCount.year == year,
        )
        if sort_order.lower() == "asc":
            statement = statement.order_by(getattr(HeadCount, sort_by).asc())
        else:
            statement = statement.order_by(getattr(HeadCount, sort_by).desc())
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)
        return list(result.scalars().all())

    async def get_summary_by_submodule(
        self, unit_id: str, year: int
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get aggregated summary statistics grouped by submodule.

        Args:
            session: Database session
            unit_id: Filter by unit ID
            status: Filter by equipment status

        Returns:
            Dict mapping submodule to summary stats:
            {
                "scientific": {
                    "total_items": 10,
                    "annual_consumption_kwh": 1500.0,
                    "total_kg_co2eq": 187.5
                },
                ...
            }
        """
        # Build query with aggregation
        query = select(
            HeadCount.submodule,
            func.count(col(HeadCount.id)).label("total_items"),
            func.sum(HeadCount.fte).label("annual_fte"),
        ).group_by(HeadCount.submodule)

        # Apply filters
        if unit_id:
            query = query.where(col(HeadCount.unit_id) == unit_id)

        # Execute query
        result = await self.session.execute(query)
        rows = result.all()

        # Convert to dict
        summary: Dict[str, Dict[str, Any]] = {}
        for submodule, total_items, annual_fte in rows:
            summary[submodule] = {
                "total_items": int(total_items),
                "annual_fte": float(annual_fte or 0),
                "annual_consumption_kwh": None,
                "total_kg_co2eq": None,
            }

        logger.debug(f"Retrieved summary for {len(summary)} submodules")

        return summary

    async def get_submodule_data(
        self,
        unit_id: str,
        year: int,
        submodule_key: str,
        limit: int,
        offset: int,
        sort_by: str,
        sort_order: str,
        filter: Optional[str] = None,
    ) -> SubmoduleResponse:
        """Get headcount record by unit_id, year, and submodule."""
        statement = select(HeadCount).where(
            HeadCount.unit_id == unit_id,
            HeadCount.submodule == submodule_key,
            # HeadCount.year == year,
        )

        if filter:
            filter.strip()
            # max filter for security
            if len(filter) > 100:
                filter = filter[:100]
            # check for empty or only-wildcard filters and handle accordingly.
            if filter == "" or filter == "%" or filter == "*":
                filter = None

        if filter:
            filter_pattern = f"%{filter}%"
            statement = statement.where(
                (col(HeadCount.display_name).ilike(filter_pattern))
            )
        if sort_order.lower() == "asc":
            statement = statement.order_by(getattr(HeadCount, sort_by).asc())
        else:
            statement = statement.order_by(getattr(HeadCount, sort_by).desc())
        statement = statement.offset(offset).limit(limit)
        result = await self.session.execute(statement)

        # Query for total count (for pagination)
        count_stmt = select(func.count()).where(
            HeadCount.unit_id == unit_id,
            HeadCount.submodule == submodule_key,
            # HeadCount.year == year,
        )
        if filter:
            count_stmt = count_stmt.where(
                (col(HeadCount.display_name).ilike(filter_pattern))
            )
        total_items = (await self.session.execute(count_stmt)).scalar_one()
        items = list(result.scalars().all())
        count = len(items)
        response = SubmoduleResponse(
            id=submodule_key,
            name=submodule_key,
            count=count,
            items=items,
            summary=SubmoduleSummary(
                total_items=total_items,
                annual_consumption_kwh=0.0,
                total_kg_co2eq=0.0,
                annual_fte=0.0,
            ),
            has_more=total_items > offset + count,
        )
        return response

    async def get_by_id(self, headcount_id: int) -> Optional[HeadCount]:
        """Get headcount record by ID."""
        statement = select(HeadCount).where(HeadCount.id == headcount_id)
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()

    async def get_by_unit_and_date(
        self, unit_id: str, date: str
    ) -> Optional[HeadCount]:
        """Get headcount record by unit_id and date."""
        statement = select(HeadCount).where(
            HeadCount.unit_id == unit_id,
            HeadCount.date == date,
        )
        result = await self.session.execute(statement)
        return result.scalar_one_or_none()
