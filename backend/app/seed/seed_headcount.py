import asyncio
import csv
from datetime import datetime
from pathlib import Path

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.headcount import HeadCount

logger = get_logger(__name__)
settings = get_settings()

CSV_PATH = Path(__file__).parent.parent.parent / "seed_data" / "seed_headcount_data.csv"


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

# All valid categories (normalized)
VALID_CATEGORIES = [
    "doctoral_assistant",
    "other",
    "postdoctoral_researcher",
    "professor",
    "scientific_collaborator",
    "student",
    "technical_administrative_staff",
    "trainee",
]


def get_role_category(french_role: str) -> str:
    """
    Get the English category for a French HR role.

    Args:
        french_role: The French HR role name

    Returns:
        The English category name (snake_case), or None if not found
    """
    return ROLE_CATEGORY_MAPPING.get(french_role, "other")


async def seed_headcount(session: AsyncSession) -> None:
    """Upsert headcount data from seed_headcount.csv."""
    logger.info("Upserting headcount data...")

    csv_path = CSV_PATH
    if not csv_path.exists():
        logger.error(f"Headcount CSV file not found at {csv_path}")
        return

    with open(csv_path, mode="r", encoding="utf-8") as csvfile:
        reader = csv.DictReader(csvfile)
        upserted = 0
        for row in reader:
            # Parse fields from CSV, adjust as needed to match your CSV columns
            date = row.get("date")
            if date:
                date = datetime.strptime(date, "%Y-%m-%d").date()
            else:
                logger.warning(f"Missing date in row: {row}")
                continue

            unit_id = row.get("unit_id")
            unit_name = row.get("unit_name")
            cf = row.get("cf")
            cf_name = row.get("cf_name")
            cf_user_id = row.get("cf_user_id")
            display_name = row.get("display_name")
            status = row.get("status")
            function = row.get("function")
            sciper = row.get("sciper")
            fte = float(row.get("fte", 0))
            submodule = row.get("submodule")
            provider = "csv"
            if not function:
                function = "other"
            function_role = get_role_category(function) or "other"
            if submodule == "student" and function_role != "student":
                function_role = "student"

            # Compose unique filter
            stmt = select(HeadCount).where(
                HeadCount.date == date,
                HeadCount.unit_id == unit_id,
                HeadCount.cf == cf,
                HeadCount.sciper == sciper,
            )
            result = await session.exec(stmt)
            existing = result.first()

            if existing:
                # Update all fields
                existing.unit_name = unit_name or ""
                existing.cf_name = cf_name or ""
                existing.cf_user_id = cf_user_id or ""
                existing.display_name = display_name or ""
                existing.status = status or ""
                existing.function = function or ""
                existing.fte = fte
                existing.submodule = submodule or ""
                existing.provider = provider
                existing.function_role = function_role or "other"
            else:
                # Insert new record
                headcount = HeadCount(
                    date=date,
                    unit_id=unit_id or "",
                    unit_name=unit_name or "",
                    cf=cf or "",
                    cf_name=cf_name or "",
                    cf_user_id=cf_user_id or "",
                    display_name=display_name or "",
                    status=status or "",
                    function=function or "",
                    sciper=sciper or "",
                    fte=fte,
                    submodule=submodule or "",
                    provider=provider,
                    function_role=function_role or "other",
                )
                session.add(headcount)
            upserted += 1

    await session.commit()
    logger.info(f"Upserted {upserted} headcount records from CSV")


async def main() -> None:
    """Main seed function."""
    logger.info("Starting equipment and emissions seeding...")

    async with SessionLocal() as session:
        await seed_headcount(session)

    logger.info("Equipment and emissions seeding complete!")


if __name__ == "__main__":
    # run script on /app/api/v1/synth_data.csv
    asyncio.run(main())
