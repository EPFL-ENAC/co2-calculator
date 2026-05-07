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

import json
import warnings
from dataclasses import dataclass
from typing import Optional
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
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


@dataclass(frozen=True)
class DedupConfig:
    """Per-job-type dedup contract for ``chain_job``.

    ``scope_columns`` are the row columns that define the unique scope
    (the partial unique index covers exactly these columns); they must
    all be non-NULL on the child row.  ``constraint_name`` matches the
    Postgres index name so a race-loss ``IntegrityError`` is logged
    with the right context.  ``job_type`` filters the pre-check so a
    different job type for the same scope can coexist with us.
    """

    job_type: str
    scope_columns: tuple[str, ...]
    constraint_name: str


AGGREGATION_DEDUP = DedupConfig(
    job_type="aggregation",
    scope_columns=("module_type_id", "year"),
    constraint_name="uq_aggregation_active",
)


EMISSION_RECALC_DEDUP = DedupConfig(
    job_type="emission_recalc",
    scope_columns=("module_type_id", "data_entry_type_id", "year"),
    constraint_name="uq_emission_recalc_active",
)


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
    dedup_config: Optional[DedupConfig] = None,
    dedup_active: Optional[bool] = None,
) -> Optional[int]:
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

    ``dedup_config`` (Plan 310-D, generalised by #1064): pre-check
    for an active row in the configured ``scope_columns`` and INSERT
    only when none exists — caller must pass non-NULL values for
    every scope column (``ValueError`` is raised otherwise).  The
    pre-check covers the common case (sequential chains within the
    same fan-out batch on the same connection); a concurrent writer
    that wins the race trips the matching partial unique index
    (``constraint_name``, which covers only NOT_STARTED/QUEUED/
    RUNNING rows) and the ``IntegrityError`` is caught and surfaced
    as the same dedup signal.  Returns ``None`` on dedup so the
    caller knows it's a no-op and skips its own follow-up fan-out;
    returns the new child id otherwise.

    ``dedup_active=True`` is a deprecated shim mapping to
    ``AGGREGATION_DEDUP`` for one release cycle; new callers should
    pass ``dedup_config=AGGREGATION_DEDUP`` directly.
    """
    if dedup_active is not None:
        # Deprecation shim — kept for one release cycle so callers
        # outside this PR's diff (and any unmerged branches) keep
        # compiling.  Maps boolean True to the original behaviour
        # (aggregation dedup); False is the no-dedup default.
        warnings.warn(
            "chain_job(dedup_active=...) is deprecated; pass "
            "dedup_config=AGGREGATION_DEDUP (or another DedupConfig) instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        if dedup_active and dedup_config is None:
            dedup_config = AGGREGATION_DEDUP

    repo = DataIngestionRepository(session)

    pipeline_id = parent.pipeline_id
    if pipeline_id is None:
        pipeline_id = uuid4()
        parent.pipeline_id = pipeline_id
        session.add(parent)
        await session.commit()

    resolved_module_type_id = (
        module_type_id if module_type_id is not None else parent.module_type_id
    )
    resolved_year = year if year is not None else parent.year

    # Plan 310-D — fail fast when caller asks for dedup but any scope
    # key is NULL.  PG treats NULLs as distinct in unique indexes by
    # default (and our partial WHERE filters NOT NULL only), so a NULL
    # would silently bypass dedup at the index level and the
    # downstream handler would then choke on the missing scope.
    # Refuse at chain_job entry instead.
    if dedup_config is not None:
        # Misconfiguration guard: a caller that passes ``job_type='X'``
        # alongside ``dedup_config=Y_DEDUP`` would have the pre-check
        # query Y while the INSERT writes X — silently disabling dedup
        # and confusing future readers of the partial unique index.
        # Refuse loudly at the entry instead.
        if job_type != dedup_config.job_type:
            raise ValueError(
                f"chain_job: job_type={job_type!r} does not match "
                f"dedup_config.job_type={dedup_config.job_type!r}.  "
                "Use the matching DedupConfig (or pass dedup_config=None)."
            )

        scope_values = {
            "module_type_id": resolved_module_type_id,
            "data_entry_type_id": data_entry_type_id,
            "year": resolved_year,
        }
        missing = [
            col for col in dedup_config.scope_columns if scope_values.get(col) is None
        ]
        if missing:
            raise ValueError(
                f"chain_job(dedup_config={dedup_config.job_type!r}): "
                f"scope keys must be set — missing {missing}; "
                f"got {scope_values}.  Pass them explicitly or ensure "
                f"the parent job has them populated."
            )

    if dedup_config is not None:
        child_id = await _insert_child_with_dedup(
            session=session,
            parent=parent,
            pipeline_id=pipeline_id,
            job_type=job_type,
            module_type_id=resolved_module_type_id,
            data_entry_type_id=data_entry_type_id,
            year=resolved_year,
            target_type=target_type,
            ingestion_method=ingestion_method,
            entity_type=entity_type,
            config=config,
            dedup_config=dedup_config,
        )
        if child_id is None:
            # Dedup hit — an active child already exists for this
            # scope.  Caller must treat None as "no-op, do not
            # fan out further" so we don't double-dispatch the
            # work the existing pending row will do.
            logger.info(
                f"chain_job(dedup): {job_type!r} for "
                f"module={resolved_module_type_id}/det={data_entry_type_id}/"
                f"year={resolved_year} already pending — skipped"
            )
            return None
    else:
        child = DataIngestionJob(
            job_type=job_type,
            module_type_id=resolved_module_type_id,
            data_entry_type_id=data_entry_type_id,
            year=resolved_year,
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
        child_id = created.id

    if child_id is None:
        # Two paths can land here:
        #   1. ``dedup_config`` already returned ``None`` above —
        #      we never reach this branch in that case (early return).
        #   2. The ORM insert path got a row back without an id (a
        #      real driver bug), or the dedup INSERT's RETURNING
        #      yielded no row despite no IntegrityError.  Either way
        #      the safety poller will pick the row up via run_after,
        #      so log loud and return ``None`` — the caller handles
        #      ``None`` as "no chain dispatched" anyway.  Returning
        #      ``-1`` here (the previous shape) was a tri-state
        #      footgun: callers had to distinguish dedup-skip vs
        #      id-missing-but-row-exists vs success.
        logger.error(
            f"chain_job: child {job_type!r} of parent {parent.id} "
            "was created without an id — relying on poller for dispatch"
        )
        return None

    # Lazy import: runner imports nothing from this module, so a
    # top-level ``from app.tasks.runner import run_job`` would be safe
    # for the static graph — but lazy here documents that ``chain_job``
    # only needs ``run_job`` for the dispatch call, not for typing or
    # construction.
    from app.tasks.runner import run_job

    fire_and_forget(run_job(child_id), name=f"run_job-{child_id}")
    return child_id


async def _insert_child_with_dedup(
    *,
    session: AsyncSession,
    parent: DataIngestionJob,
    pipeline_id,
    job_type: str,
    module_type_id: Optional[int],
    data_entry_type_id: Optional[int],
    year: Optional[int],
    target_type: TargetType,
    ingestion_method: IngestionMethod,
    entity_type: EntityType,
    config: Optional[dict],
    dedup_config: DedupConfig,
) -> Optional[int]:
    """Pre-check + INSERT, falling back to IntegrityError on race.

    Returns the new child id on success, or ``None`` when the partial
    unique index named by ``dedup_config.constraint_name`` already
    covers an active (NOT_STARTED/QUEUED/RUNNING) row for the same
    scope.

    Why pre-check + INSERT rather than ``INSERT ... ON CONFLICT DO
    NOTHING``: PG's ON CONFLICT inference for partial indexes
    requires the inferred predicate to imply the index's WHERE
    clause, and the implied-by check stumbles on nullable columns
    (the scope columns are nullable on the table even though our
    partial WHERE filters NOT NULL only).  The pre-check handles
    the common case (sequential chains within the same fan-out
    batch on the same connection); the ``IntegrityError`` catch
    covers the genuine concurrent race so the first writer wins
    regardless of interleaving.

    Implemented as raw SQL because SQLModel's ORM-level insert path
    doesn't expose the ON CONFLICT clause cleanly for partial indexes.
    The raw INSERT bypasses the model_validate hook in
    ``DataIngestionRepository.create_ingestion_job`` — that's fine
    here because the columns we set are the only ones the model
    requires for a NOT_STARTED row (state has a server default but
    we always pass it explicitly to keep the SQL self-documenting).
    """

    # asyncpg accepts UUID objects directly via type adapters, but
    # raw text SQL coerces best when stringified.
    pipeline_id_str = str(pipeline_id) if pipeline_id is not None else None
    meta_json = json.dumps({"config": config or {}, "parent_job_id": parent.id})

    # The chain_job entry guard already rejected NULL scope values,
    # so simple equality is sufficient here — no ``(:col IS NULL AND
    # col IS NULL)`` branch needed.
    scope_param_map = {
        "module_type_id": module_type_id,
        "data_entry_type_id": data_entry_type_id,
        "year": year,
    }
    scope_predicate = " AND ".join(
        f"{col} = :{col}" for col in dedup_config.scope_columns
    )
    pre_check_params = {
        col: scope_param_map[col] for col in dedup_config.scope_columns
    }
    pre_check_params["job_type"] = dedup_config.job_type

    pre_check = text(
        f"""
        SELECT 1
        FROM data_ingestion_jobs
        WHERE job_type = :job_type
          AND {scope_predicate}
          AND state IN (
              'NOT_STARTED'::ingestion_state_enum,
              'QUEUED'::ingestion_state_enum,
              'RUNNING'::ingestion_state_enum
          )
        LIMIT 1
        """
    )
    existing = await session.execute(pre_check, pre_check_params)
    if existing.first() is not None:
        # Active row already pending — caller treats None as "no-op".
        return None

    # No active row found in the pre-check; INSERT and let the partial
    # unique index trip ``IntegrityError`` if a concurrent writer beat
    # us.  We catch it below and surface as the same dedup signal.
    # ``provider`` is NOT NULL on the table; inherit from the parent
    # to keep the audit shape consistent (the chain represents work
    # spawned by the same actor as the parent ingest job).
    sql = text(
        """
        INSERT INTO data_ingestion_jobs (
            job_type, module_type_id, data_entry_type_id, year,
            target_type, ingestion_method, entity_type, provider, state,
            is_current, pipeline_id, run_after, meta
        )
        VALUES (
            :job_type, :module_type_id, :data_entry_type_id, :year,
            :target_type, :ingestion_method, :entity_type, :provider,
            'NOT_STARTED'::ingestion_state_enum,
            FALSE, CAST(:pipeline_id AS UUID), NULL,
            CAST(:meta AS JSONB)
        )
        RETURNING id
        """
    )
    # Native PG enum columns store the enum *name*, not the int value
    # — the SAEnum spec passes ``name=...`` and ``native_enum=True`` so
    # the on-disk representation is the label.  ``IngestionState`` is
    # written via the literal ``'NOT_STARTED'::ingestion_state_enum``
    # cast in the SQL above; the other three need ``.name`` here.
    parent_provider = getattr(parent, "provider", None)
    provider_value = (
        parent_provider.name
        if parent_provider is not None and hasattr(parent_provider, "name")
        else parent_provider
    )

    try:
        result = await session.execute(
            sql,
            {
                "job_type": job_type,
                "module_type_id": module_type_id,
                "data_entry_type_id": data_entry_type_id,
                "year": year,
                "target_type": target_type.name,
                "ingestion_method": ingestion_method.name,
                "entity_type": entity_type.name,
                "provider": provider_value,
                "pipeline_id": pipeline_id_str,
                "meta": meta_json,
            },
        )
    except IntegrityError as exc:
        # Narrow the catch to the configured partial unique index.
        # A blanket catch would swallow unrelated NOT NULL / FK / enum
        # violations and silently skip dispatching the chained child —
        # treat anything other than the expected dedup constraint as a
        # real bug worth bubbling up.
        msg = str(getattr(exc.orig, "diag", None) or exc).lower()
        if dedup_config.constraint_name.lower() not in msg:
            await session.rollback()
            raise
        logger.info(
            f"chain_job(dedup): {job_type!r} for "
            f"module={module_type_id}/det={data_entry_type_id}/year={year} "
            f"lost partial-unique-index race ({dedup_config.constraint_name})"
            " — sibling owns the row"
        )
        await session.rollback()
        return None

    row = result.first()
    await session.commit()
    # ``RETURNING id`` always yields a row when the INSERT succeeds
    # (the pre-check + IntegrityError catch already cover the dedup
    # paths), so a None here would be a real driver bug — surface it.
    if row is None:
        logger.error(
            f"chain_job(dedup): {job_type!r} for "
            f"module={module_type_id}/det={data_entry_type_id}/year={year} "
            "— INSERT RETURNING yielded no row despite no "
            "IntegrityError; treating as dedup hit but please investigate"
        )
        return None
    return int(row[0])
