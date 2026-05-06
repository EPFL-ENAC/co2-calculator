"""Plan 310-C ``chain_job`` — parent → child handoff helper.

Extracted from ``app.tasks.runner`` to break the static import cycle
flagged by CodeQL (alerts #644/#645/#646).  The cycle was:

    ingestion_tasks (top-level) → runner (top-level for chain_job)
    runner             (lazy in run_job) → bootstrap
    bootstrap          (lazy in bootstrap_handlers) → ingestion_tasks

Moving ``chain_job`` to its own module replaces the top-level
``ingestion_tasks → runner`` edge with a top-level
``ingestion_tasks → _chain`` edge.  ``_chain`` lazy-imports
``run_job`` from ``runner`` only inside the function body (so
``fire_and_forget`` can schedule the child) — that lazy edge does not
participate in any other cycle, and CodeQL's ``py/cyclic-import`` rule
keys on top-level imports.

Why a dedicated module instead of co-locating with ``ingestion_tasks``:
``chain_job`` is a generic helper used by every handler that wants to
fan out children (today ``factor_ingest``; tomorrow the aggregation
handler from Plan 310-D).  Living next to the handlers couples it to
the ingest provider machinery; living in its own module keeps the
contract narrow (parent + child shape + dispatch).
"""

from typing import Optional
from uuid import uuid4

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.logging import get_logger
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.repositories.data_ingestion import DataIngestionRepository
from app.tasks._background import fire_and_forget

logger = get_logger(__name__)


async def chain_job(
    parent: DataIngestionJob,
    *,
    job_type: str,
    session: AsyncSession,
    module_type_id: Optional[int] = None,
    data_entry_type_id: Optional[int] = None,
    year: Optional[int] = None,
    config: Optional[dict] = None,
    target_type: TargetType = TargetType.DATA_ENTRIES,
    ingestion_method: IngestionMethod = IngestionMethod.computed,
    entity_type: EntityType = EntityType.MODULE_PER_YEAR,
) -> int:
    """Create a child job and fire it through ``run_job``.

    Inherits the parent's ``pipeline_id`` (or generates a fresh UUID
    if the parent has none yet — the first chain on an ad-hoc run
    starts the pipeline).  The child is created NOT_STARTED with
    ``run_after=None`` (NULL means "runnable immediately"; the
    safety poller's claim WHERE treats NULL as eligible, so it can
    pick the row up if this pod crashes between the commit and the
    ``fire_and_forget``).

    Defaults match the most common case (an ``emission_recalc``
    child of an ingest parent: same module, scoped to a single det,
    DATA_ENTRIES target, computed source).  ``module_type_id`` and
    ``year`` inherit from the parent when the caller passes ``None``.
    ``data_entry_type_id`` does NOT inherit by design: a multi-det
    parent (e.g. a FACTORS ingest spanning several dets) fans out to
    one child per det, so the caller must always pass the specific
    child det.  Callers override the rest as they need.

    Returns the child's ``id``.  Persists the parent's
    ``pipeline_id`` if it had to generate one — without that, a
    pod-crash-then-recovery-claim of the parent would generate a
    different UUID and the child would be orphaned from the parent's
    run.
    """
    repo = DataIngestionRepository(session)

    pipeline_id = parent.pipeline_id
    if pipeline_id is None:
        pipeline_id = uuid4()
        parent.pipeline_id = pipeline_id
        session.add(parent)
        await session.commit()

    child = DataIngestionJob(
        job_type=job_type,
        module_type_id=(
            module_type_id if module_type_id is not None else parent.module_type_id
        ),
        data_entry_type_id=data_entry_type_id,
        year=year if year is not None else parent.year,
        target_type=target_type,
        ingestion_method=ingestion_method,
        entity_type=entity_type,
        state=IngestionState.NOT_STARTED,
        is_current=False,
        pipeline_id=pipeline_id,
        # ``None`` means "runnable immediately" — claim_job's WHERE
        # treats NULL run_after as eligible.  Matches the existing
        # ingestion_tasks.py recalc-job creation pattern.
        run_after=None,
        meta={"config": config or {}, "parent_job_id": parent.id},
    )
    created = await repo.create_ingestion_job(child)
    await session.commit()

    if created.id is None:
        # Defensive: create_ingestion_job should always return a
        # row with id set after commit.  If it ever doesn't, the
        # safety poller will pick up the row anyway via run_after.
        logger.error(
            f"chain_job: child {job_type!r} of parent {parent.id} "
            "was created without an id — relying on poller for dispatch"
        )
        return -1

    # Lazy import: runner imports nothing from this module, so a
    # top-level ``from app.tasks.runner import run_job`` would be safe
    # for the static graph — but lazy here documents that ``chain_job``
    # only needs ``run_job`` for the dispatch call, not for typing or
    # construction.
    from app.tasks.runner import run_job

    fire_and_forget(run_job(created.id), name=f"run_job-{created.id}")
    return created.id
