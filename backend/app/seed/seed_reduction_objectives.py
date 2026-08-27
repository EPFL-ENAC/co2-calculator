"""Seed the three reduction-objective CSVs and the institutional goals.

Replays what an operator does in backoffice → Configuration → Reduction
objectives: upload the institutional footprint, the population forecast and
the unit scenarios, then enter the reduction goals.  Both endpoints
(``POST /year-configuration/{year}/upload`` and ``PATCH
/year-configuration/{year}``) write into the same
``year_configuration.config['reduction_objectives']`` blob, so the seed
writes that blob directly — reusing the endpoints' own CSV validator and
storage-path helpers so the two can't drift.
"""

import asyncio
import copy
import shutil
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1.year_configuration import (
    generate_unique_filename,
    get_files_storage_path,
)
from app.core.logging import get_logger
from app.db import SessionLocal
from app.models.user import UserProvider
from app.models.year_configuration import YearConfiguration
from app.schemas.year_configuration import (
    ReductionObjectiveGoal,
    validate_reduction_objective_csv,
)

logger = get_logger(__name__)

INPUT_DATA_FOLDER = Path(__file__).parent.parent.parent / "INPUT_DATA"

# Category → source CSV.  Categories are the ``FileCategory`` literals the
# upload endpoint accepts.
CSV_BY_CATEGORY: dict[str, Path] = {
    "footprint": INPUT_DATA_FOLDER / "reduction_obj_epfl_footprint(in).csv",
    "population": INPUT_DATA_FOLDER / "reduction_obj_population_forecast(in).csv",
    "scenarios": INPUT_DATA_FOLDER / "reduction_obj_unit_scenarios_reduction(in).csv",
}

# Same mapping the upload endpoint applies before writing into the config.
CONFIG_KEY_BY_CATEGORY: dict[str, str] = {
    "footprint": "institutional_footprint",
    "population": "population_projections",
    "scenarios": "unit_scenarios",
}

DEFAULT_GOALS: list[ReductionObjectiveGoal] = [
    ReductionObjectiveGoal(
        target_year=2030, reduction_percentage=0.1, reference_year=2016
    ),
    ReductionObjectiveGoal(
        target_year=2035, reduction_percentage=0.1, reference_year=2016
    ),
    ReductionObjectiveGoal(
        target_year=2040, reduction_percentage=0.1, reference_year=2016
    ),
]


def _store_file(source: Path, category: str) -> dict[str, str]:
    """Copy a CSV into the files store under the endpoint's own layout.

    Returns the ``{path, filename, uploaded_at}`` metadata dict that
    ``upload_reduction_objective_file`` writes into
    ``reduction_objectives.files[<key>]``.
    """
    storage_root = Path(get_files_storage_path()).resolve()
    category_dir = f"reduction_objectives/{category}"
    target_dir = storage_root / category_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    unique_filename = generate_unique_filename(source.name)
    shutil.copyfile(source, target_dir / unique_filename)

    return {
        "path": f"{category_dir}/{unique_filename}",
        "filename": unique_filename,
        "uploaded_at": datetime.utcnow().isoformat(),
    }


async def seed_reduction_objectives(
    session: AsyncSession,
    year: int,
    provider: UserProvider,
    goals: Sequence[ReductionObjectiveGoal] = tuple(DEFAULT_GOALS),
) -> None:
    """Fill the three reduction-objective files and the goals for one year."""
    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == provider,
    )
    row = (await session.exec(stmt)).first()
    if row is None:
        raise ValueError(
            f"No year_configuration row for year={year} provider={provider.name} — "
            "create the year before seeding its reduction objectives"
        )

    # Same invariant PATCH /year-configuration/{year} enforces.
    for goal in goals:
        if goal.target_year <= year:
            raise ValueError(
                f"Goal target_year ({goal.target_year}) must be greater than "
                f"configuration year ({year})"
            )

    config: dict[str, Any] = copy.deepcopy(row.config)
    objectives = config.setdefault("reduction_objectives", {})
    files = objectives.setdefault("files", {})

    for category, source in CSV_BY_CATEGORY.items():
        if not source.is_file():
            raise FileNotFoundError(f"Reduction-objective CSV not found: {source}")
        # Raises ValueError(list[str]) on a bad header or any bad row.
        rows = validate_reduction_objective_csv(source.read_bytes(), category)
        config_key = CONFIG_KEY_BY_CATEGORY[category]
        files[config_key] = _store_file(source, category)
        objectives[config_key] = rows
        print(f"Loaded {len(rows)} {config_key} rows for {year}")

    objectives["goals"] = [goal.model_dump() for goal in goals]

    # Whole-dict reassignment so SQLAlchemy detects the JSON column change.
    row.config = config
    session.add(row)
    logger.info(
        f"Seeded reduction objectives for {year}: "
        f"{len(goals)} goals, {len(CSV_BY_CATEGORY)} files."
    )


async def main(year: int, provider: UserProvider = UserProvider.ACCRED) -> None:
    async with SessionLocal() as session:
        await seed_reduction_objectives(session, year, provider)
        await session.commit()


if __name__ == "__main__":
    asyncio.run(main(2025))
