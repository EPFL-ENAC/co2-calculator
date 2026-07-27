"""Planner purchase factors, derived from the Calculator's.

The planner prices a budget with one average EF per category, plus one for a
global budget; the Calculator stores one EF per procurement code. A category's
planner factor is the mean over its codes, and the global one is the mean of
those category means — so it weights categories equally rather than following
whichever category happens to carry the most codes.

Both sides are per EUR, the currency the Calculator's purchase factors are
uploaded in, so nothing is converted anywhere.

Derivation runs as part of a purchase factor upload, for the year that upload
covers — planner reports resolve every factor from their reference year, so a
plan whose reference year has no Calculator purchase factors resolves nothing.
"""

from collections.abc import Mapping, Sequence

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_entry import DataEntryTypeEnum
from app.models.factor import Factor
from app.modules.emissions import EmissionType
from app.modules_planner.purchase.emissions import PLANNER_PURCHASE_EMISSIONS
from app.repositories.factor_repo import FactorRepository

logger = get_logger(__name__)

# The planner's category slugs are the Calculator's purchase entry types by
# the same name — derived, so the two cannot drift.
SOURCE_TYPE_BY_CATEGORY: dict[str, DataEntryTypeEnum] = {
    category: DataEntryTypeEnum[category] for category in PLANNER_PURCHASE_EMISSIONS
}
PURCHASE_SOURCE_TYPES: frozenset[DataEntryTypeEnum] = frozenset(
    SOURCE_TYPE_BY_CATEGORY.values()
)

SOURCE_EF_KEY = "ef_kg_co2eq_per_currency"
PLANNER_EF_KEY = "ef_kg_co2eq_per_eur"


def category_means(
    efs_by_category: Mapping[str, Sequence[float]],
) -> dict[str, float]:
    """The mean EF of each category that the year has factors for.

    A category with none is left out rather than defaulted: the planner then
    shows it as unpriced, which is what it is.
    """
    return {
        category: sum(efs) / len(efs)
        for category, efs in efs_by_category.items()
        if efs
    }


def global_mean(means: Mapping[str, float]) -> float:
    """The global budget weights every category equally, not every code."""
    return sum(means.values()) / len(means)


def build_factors(means: Mapping[str, float], year: int) -> list[Factor]:
    """One factor per priced category, plus the global-budget one."""
    factors = [
        Factor(
            emission_type_id=PLANNER_PURCHASE_EMISSIONS[category].value,
            data_entry_type_id=DataEntryTypeEnum.planner_purchase.value,
            classification={"purchase_category": category},
            values={PLANNER_EF_KEY: round(mean, 6)},
            year=year,
        )
        for category, mean in means.items()
    ]
    factors.append(
        Factor(
            emission_type_id=EmissionType.purchases__goods_and_services.value,
            data_entry_type_id=DataEntryTypeEnum.planner_purchase_budget.value,
            classification={},
            values={PLANNER_EF_KEY: round(global_mean(means), 6)},
            year=year,
        )
    )
    return factors


async def _collect_source_efs(
    session: AsyncSession, year: int
) -> dict[str, list[float]]:
    """Read the Calculator's purchase factors for ``year``, keyed by category."""
    category_by_type = {
        source.value: category for category, source in SOURCE_TYPE_BY_CATEGORY.items()
    }
    stmt = select(Factor).where(
        col(Factor.data_entry_type_id).in_(list(category_by_type)),
        col(Factor.year) == year,
    )
    efs: dict[str, list[float]] = {category: [] for category in SOURCE_TYPE_BY_CATEGORY}
    for factor in (await session.exec(stmt)).all():
        ef = factor.values.get(SOURCE_EF_KEY)
        if ef is None:
            raise ValueError(
                f"Factor {factor.id} carries no {SOURCE_EF_KEY} — cannot average it "
                "into a planner purchase factor"
            )
        efs[category_by_type[factor.data_entry_type_id]].append(float(ef))
    return efs


async def derive_planner_purchase_factors(
    session: AsyncSession, year: int, job_id: int | None
) -> int:
    """Recompute the planner purchase factors for ``year``. Returns rows written.

    Upserts on the factor identity key, so the rows keep their ids across
    re-uploads and the emissions pointing at them stay valid. Runs in the
    caller's transaction.
    """
    means = category_means(await _collect_source_efs(session, year))
    if not means:
        raise ValueError(
            f"No Calculator purchase factors for {year} to derive planner "
            "purchase factors from"
        )
    affected = await FactorRepository(session).upsert_factors(
        build_factors(means, year), job_id
    )
    logger.info(f"Derived {affected} planner purchase factors for {year}")
    return affected
