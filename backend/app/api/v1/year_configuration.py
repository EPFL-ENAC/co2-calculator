"""Year configuration API endpoints."""

import copy
import hashlib
import io
import os
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.core.security import is_permitted
from app.core.submodule_mandatoriness import (
    MODULES_REQUIRING_COMMON_FACTOR,
    get_submodule_mandatoriness,
)
from app.models.audit import AuditChangeTypeEnum, AuditDocument
from app.models.data_entry import DataEntryTypeEnum
from app.models.data_ingestion import (
    DataIngestionJob,
    EntityType,
    IngestionMethod,
    IngestionState,
    TargetType,
)
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.models.year_configuration import YearConfiguration
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.year_configuration import (
    FileCategory,
    FileMetadata,
    FileUploadResponse,
    ModuleRecalculationStatusEntry,
    RecalculationStatusEntry,
    SyncJobSummary,
    YearConfigurationCreate,
    YearConfigurationListItem,
    YearConfigurationResponse,
    YearConfigurationUpdate,
    validate_reduction_objective_csv,
)
from app.services.year_config_service import (
    check_threshold_exceeded,
    generate_default_year_config,
    get_module_config,
    get_submodule_config,
)
from app.tasks._background import fire_and_forget
from app.tasks.runner import run_job

logger = get_logger(__name__)
router = APIRouter()


def _build_job_lookup(
    jobs: list,
) -> dict[tuple[int | None, int | None, int | None, int | None], "SyncJobSummary"]:
    """Build a lookup dict from latest jobs keyed by
    (module, data_entry, target, method) IDs.

    Args:
        jobs: List of DataIngestionJob objects.

    Returns:
        Dict mapping (module_type_id, data_entry_type_id, target_type,
        ingestion_method) to SyncJobSummary.
    """
    lookup: dict[
        tuple[int | None, int | None, int | None, int | None], SyncJobSummary
    ] = {}
    for job in jobs:
        if job.id is None:
            continue
        target_val = job.target_type.value if job.target_type is not None else None
        # The year-config view's ``latest_data_job`` reflects per-year
        # (module-level) uploads only.  Unit-specific data uploads
        # (ModuleUnitSpecificCSVProvider, entity_type=MODULE_UNIT_SPECIFIC)
        # are per-unit work done on the module page; skip them so they
        # neither surface as nor mask the module-level data job (they'd
        # otherwise collide on the same lookup key).
        if (
            target_val == TargetType.DATA_ENTRIES.value
            and job.entity_type == EntityType.MODULE_UNIT_SPECIFIC
        ):
            continue
        method_val = (
            job.ingestion_method.value if job.ingestion_method is not None else 0
        )
        key = (job.module_type_id, job.data_entry_type_id, target_val, method_val)
        lookup[key] = SyncJobSummary(
            job_id=job.id,
            module_type_id=job.module_type_id,
            data_entry_type_id=job.data_entry_type_id,
            year=job.year,
            ingestion_method=method_val,
            target_type=target_val,
            state=job.state.value if job.state is not None else None,
            result=job.result.value if job.result is not None else None,
            status_message=job.status_message,
            meta=job.meta,
        )
    return lookup


def _enrich_config_with_jobs(
    config: dict,
    job_lookup: dict[
        tuple[int | None, int | None, int | None, int | None], SyncJobSummary
    ],
) -> dict:
    """Inject per-target-type latest jobs into each submodule of the config dict.

    Args:
        config: Year configuration dict (modules → submodules).
        job_lookup: Mapping from
            (module_type_id, data_entry_type_id, target_type, ingestion_method)
            to job summary.

    Returns:
        Enriched config dict (mutated in-place for efficiency).
    """
    target_type_map = {
        0: "latest_data_job",
        1: "latest_factor_job",
        3: "latest_reference_job",
    }
    INGESTION_METHOD_API = 0
    common_target_type_map = {
        0: "latest_common_data_job",
        1: "latest_common_factor_job",
    }
    modules = config.get("modules", {})
    for module_key, module_val in modules.items():
        if not isinstance(module_val, dict):
            continue
        try:
            m_id = int(module_key)
        except (ValueError, TypeError):
            continue
        submodules = module_val.get("submodules", {})
        for sub_key, sub_val in submodules.items():
            if not isinstance(sub_val, dict):
                continue
            try:
                s_id = int(sub_key)
            except (ValueError, TypeError):
                continue
            for target_val, field_name in target_type_map.items():
                job = _pick_latest_job(job_lookup, m_id, s_id, target_val)
                sub_val[field_name] = job.model_dump() if job else None
            api_data_job = job_lookup.get((m_id, s_id, 0, INGESTION_METHOD_API))
            sub_val["latest_api_data_job"] = (
                api_data_job.model_dump() if api_data_job else None
            )
        for target_val, field_name in common_target_type_map.items():
            common_job = _pick_latest_job(job_lookup, m_id, None, target_val)
            module_val[field_name] = common_job.model_dump() if common_job else None
    return config


def _enrich_config_with_incomplete_flags(config: dict) -> dict:
    """Inject backend-computed ``incomplete`` + ``incomplete_reasons`` per #1215.

    A submodule is incomplete iff a *mandatory* upload (factor or
    reference) is missing. An errored job (``result == 2``) is NOT
    missing — the upload-card surfaces error state independently.
    Must run after ``_enrich_config_with_jobs`` (depends on the
    ``latest_*_job`` keys it writes).
    """
    for module_key, module_val in config.get("modules", {}).items():
        if not isinstance(module_val, dict):
            continue
        try:
            module_type_id = int(module_key)
        except (ValueError, TypeError):
            continue
        _annotate_module_incomplete(module_val, module_type_id)
    return config


def _annotate_module_incomplete(module_val: dict, module_type_id: int) -> None:
    """Annotate each submodule, then roll up to the module's ``incomplete``.

    Disabled modules carry ``incomplete=False`` regardless of state —
    matches the legacy frontend gate.
    """
    common_factor_present = module_val.get("latest_common_factor_job") is not None
    any_enabled_incomplete = False
    submodules = module_val.get("submodules", {})
    if isinstance(submodules, dict):
        for sub_key, sub_val in submodules.items():
            if not isinstance(sub_val, dict):
                continue
            try:
                data_entry_type_id = int(sub_key)
            except (ValueError, TypeError):
                continue
            reasons = _submodule_incomplete_reasons(
                sub_val, module_type_id, data_entry_type_id, common_factor_present
            )
            sub_val["incomplete"] = bool(reasons)
            sub_val["incomplete_reasons"] = reasons
            if reasons and sub_val.get("enabled", True):
                any_enabled_incomplete = True
    if not module_val.get("enabled", True):
        module_val["incomplete"] = False
        return
    needs_common = (
        module_type_id in MODULES_REQUIRING_COMMON_FACTOR and not common_factor_present
    )
    module_val["incomplete"] = any_enabled_incomplete or needs_common


def _submodule_incomplete_reasons(
    sub_val: dict,
    module_type_id: int,
    data_entry_type_id: int,
    common_factor_present: bool,
) -> list[str]:
    """Return missing-mandatory reasons for one submodule.

    A mandatory factor is satisfied by either the submodule's own
    ``latest_factor_job`` or the module's ``latest_common_factor_job``
    (matches the legacy frontend rule). Reference has no such fallback.
    """
    rules = get_submodule_mandatoriness(module_type_id, data_entry_type_id)
    reasons: list[str] = []
    has_factor = sub_val.get("latest_factor_job") is not None or common_factor_present
    if rules.mandatory_factor and not has_factor:
        reasons.append("missing_factor")
    if rules.mandatory_reference and sub_val.get("latest_reference_job") is None:
        reasons.append("missing_reference")
    return reasons


def _pick_latest_job(
    job_lookup: dict[
        tuple[int | None, int | None, int | None, int | None], SyncJobSummary
    ],
    module_id: int,
    sub_id: int | None,
    target_val: int,
) -> SyncJobSummary | None:
    """Pick the latest job for a given target type.

    For target=DATA_ENTRIES, only CSV uploads surface here: API has its own
    field (``latest_api_data_job``); MANUAL is reserved for seed-data
    scripts; COMPUTED targets factor recompute, not data. Restricting to CSV
    prevents a failed API ingestion from masking a successful CSV upload.
    For factor/reference targets, all methods are considered (API preferred
    via the existing ingestion_method ascending sort).
    """
    INGESTION_METHOD_CSV = 1
    TARGET_DATA_ENTRIES = 0

    candidates = [
        v
        for k, v in job_lookup.items()
        if k[0] == module_id
        and k[1] == sub_id
        and k[2] == target_val
        and (target_val != TARGET_DATA_ENTRIES or k[3] == INGESTION_METHOD_CSV)
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda j: j.ingestion_method)
    return candidates[0]


def _build_recalculation_status(
    rows: list,
) -> list[ModuleRecalculationStatusEntry]:
    """Build per-module recalculation status from repository rows.

    Plan 310-D / Issue #1062 — ``current_pipeline_id`` no longer rides
    here; the frontend reads the active pipeline_id from the unified
    ``pipelineStateStore`` (``GET /v1/sync/active-pipelines``).  This
    helper now produces the pure recalculation-status rollup.

    Args:
        rows: List of RecalculationStatusRow dicts from the repository.

    Returns:
        List of ModuleRecalculationStatusEntry grouped by module_type_id.
    """
    modules: dict[int, list[RecalculationStatusEntry]] = {}
    for row in rows:
        module_id = row["module_type_id"]
        if module_id not in modules:
            modules[module_id] = []
        modules[module_id].append(
            RecalculationStatusEntry(
                module_type_id=row["module_type_id"],
                data_entry_type_id=row["data_entry_type_id"],
                year=row["year"],
                needs_recalculation=row["needs_recalculation"],
                last_factor_job_id=row["last_factor_job_id"],
                last_factor_job_result=row["last_factor_job_result"],
                last_recalculation_job_id=row["last_recalculation_job_id"],
                last_recalculation_job_result=row["last_recalculation_job_result"],
            )
        )
    return [
        ModuleRecalculationStatusEntry(
            module_type_id=module_id,
            year=dets[0].year if dets else 0,
            needs_recalculation=any(det.needs_recalculation for det in dets),
            data_entry_types=dets,
        )
        for module_id, dets in modules.items()
    ]


def get_files_storage_path() -> str:
    """Get the files storage path from environment or default."""
    return os.environ.get("FILES_STORAGE_PATH", "./files_storage")


def _deep_merge(base: Dict[str, Any], patch: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively merge patch into base (returns a new dict).

    For each key in patch:
    - If both base[key] and patch[key] are dicts, recurse.
    - Otherwise, patch[key] overwrites base[key].

    Args:
        base: Original dict.
        patch: Partial dict to merge in.

    Returns:
        New merged dict (base is not mutated).
    """
    merged = base.copy()
    for key, value in patch.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename preserving extension.

    Uses os.path.basename to strip any directory components supplied by the
    caller before appending a UUID, preventing path-traversal via filenames.
    """
    safe_name = os.path.basename(original_filename)
    name, ext = os.path.splitext(safe_name)
    return f"{name}_{uuid4().hex}{ext}"


async def save_uploaded_file(
    file: UploadFile, category: FileCategory, year: int
) -> FileMetadata:
    """Save uploaded file to storage and return metadata.

    Args:
        file: Uploaded file.
        category: File category (footprint, population, scenarios).
        year: Configuration year.

    Returns:
        FileMetadata with path, filename, and upload timestamp.
    """
    storage_path = os.path.realpath(get_files_storage_path())
    category_dir = f"reduction_objectives/{category}"
    full_path = os.path.normpath(os.path.join(storage_path, category_dir))

    # Guard against path traversal: the resolved path must stay inside storage_path.
    if not full_path.startswith(storage_path + os.sep):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file category path.",
        )

    # Create directory if it doesn't exist
    os.makedirs(full_path, exist_ok=True)

    # Generate unique filename (basename-sanitised internally)
    unique_filename = generate_unique_filename(file.filename or "uploaded_file")
    file_path = os.path.normpath(os.path.join(full_path, unique_filename))

    # Second guard: the final file path must also stay inside storage_path.
    if not file_path.startswith(storage_path + os.sep):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename.",
        )

    # Save file
    content = await file.read()
    with open(file_path, "wb") as f:
        f.write(content)

    # Return metadata
    return FileMetadata(
        path=os.path.join(category_dir, unique_filename),
        filename=unique_filename,
        uploaded_at=datetime.utcnow().isoformat(),
    )


async def create_audit_entry(
    session: AsyncSession,
    year: int,
    change_type: AuditChangeTypeEnum,
    user: User,
    data_snapshot: Dict[str, Any],
    data_diff: Dict[str, Any] | None = None,
) -> None:
    """Create audit entry for year configuration change.

    ``YearConfiguration`` is keyed by ``(year, provider)``; the audit chain
    must mirror that so two providers don't interleave their version
    counters. Encode ``entity_id`` as ``year * 10 + provider.value`` —
    ``UserProvider`` is 0/1/2 so this stays collision-free with adjacent
    years. The ``data_snapshot`` always includes ``provider`` so the
    encoded id is recoverable.
    """
    entity_id = year * 10 + int(user.provider)

    # Calculate hash for integrity chain
    snapshot_str = str(data_snapshot)
    current_hash = hashlib.sha256(snapshot_str.encode()).hexdigest()

    # Get previous version hash if updating
    previous_hash = None
    stmt = (
        select(AuditDocument)
        .where(col(AuditDocument.entity_type) == "year_configuration")
        .where(col(AuditDocument.entity_id) == entity_id)
        .where(col(AuditDocument.is_current))
        .order_by(col(AuditDocument.version).desc())
    )
    result = (await session.exec(stmt)).first()

    if result:
        previous_hash = result.current_hash
        # Mark previous version as not current
        result.is_current = False
        session.add(result)
        new_version = result.version + 1
    else:
        new_version = 1

    # Create new audit entry
    audit_entry = AuditDocument(
        entity_type="year_configuration",
        entity_id=entity_id,
        version=new_version,
        is_current=True,
        data_snapshot=data_snapshot,
        data_diff=data_diff,
        change_type=change_type,
        changed_by=user.id,
        changed_at=datetime.utcnow(),
        handler_id=user.institutional_id,
        handled_ids=[user.institutional_id],
        ip_address="127.0.0.1",
        route_path=f"/api/v1/year-configuration/{year}",
        previous_hash=previous_hash,
        current_hash=current_hash,
    )

    session.add(audit_entry)


@router.get(
    "/",
    response_model=list[YearConfigurationListItem],
    status_code=status.HTTP_200_OK,
)
async def list_year_configurations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List year configurations available to the caller.

    Results are always scoped to ``current_user.provider`` — a TEST user
    never sees ACCRED rows and vice versa. Backoffice data managers
    additionally bypass the ``is_started`` filter (regular users only
    see opened years). This is what drives the workspace year selector
    — closed years stay hidden from regular users until backoffice
    opens them.

    Sorted by year descending (latest first).
    """
    is_admin = await is_permitted(current_user, "backoffice.configuration", "view")

    stmt = select(YearConfiguration).where(
        col(YearConfiguration.provider) == current_user.provider
    )
    if not is_admin:
        stmt = stmt.where(col(YearConfiguration.is_started).is_(True))
    stmt = stmt.order_by(col(YearConfiguration.year).desc())

    rows = (await db.exec(stmt)).all()
    return [YearConfigurationListItem.model_validate(r) for r in rows]


@router.get(
    "/{year}",
    response_model=YearConfigurationResponse,
    status_code=status.HTTP_200_OK,
)
async def get_year_configuration(
    year: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch year configuration for the given year, enriched with latest sync jobs.

    Each submodule in the response includes `latest_data_job`, `latest_factor_job`,
    and `latest_reference_job` fields with the most recent ingestion job summary
    per target type. This eliminates the need for a separate call to
    `/sync/jobs/year/{year}/latest`.

    Returns 404 if no configuration has been created yet.
    Backoffice users can then create it via POST /{year}.

    Args:
        year: Configuration year.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Year configuration enriched with latest sync job per submodule.
    """
    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == current_user.provider,
    )
    result = (await db.exec(stmt)).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No configuration found for year {year}",
        )

    repo = DataIngestionRepository(db)
    latest_jobs = await repo.get_latest_jobs_by_year(year)
    job_lookup = _build_job_lookup(latest_jobs)

    enriched_config = copy.deepcopy(result.config)
    _enrich_config_with_jobs(enriched_config, job_lookup)
    _enrich_config_with_incomplete_flags(enriched_config)

    recalc_rows = await repo.get_recalculation_status_by_year(year)
    recalculation_status = _build_recalculation_status(recalc_rows)

    return YearConfigurationResponse(
        year=result.year,
        is_started=result.is_started,
        configuration_completed=result.configuration_completed,
        config=enriched_config,
        recalculation_status=recalculation_status,
        updated_at=result.updated_at,
    )


@router.post(
    "/{year}",
    response_model=YearConfigurationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_year_configuration(
    year: int,
    payload: YearConfigurationCreate | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create initial year configuration.

    Only accessible to super administrators (CO2_SUPERADMIN).
    Returns 409 if a configuration already exists for the year.

    Args:
        year: Configuration year.
        payload: Optional initial configuration. Defaults to generated config.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Created year configuration.
    """
    if not await is_permitted(current_user, "backoffice.configuration", "edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super administrators can create year configurations",
        )

    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == current_user.provider,
    )
    existing = (await db.exec(stmt)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Configuration for year {year} provider "
                f"{current_user.provider.name} already exists"
            ),
        )

    config_data = (
        payload.config if payload and payload.config else generate_default_year_config()
    )
    # Issue #867 — collapse the old two-click flow ("Create year" then
    # "Sync units from Accred") into a single observable pipeline.  The
    # endpoint auto-enqueues a ``unit_sync`` ``DataIngestionJob`` with
    # a freshly-minted ``pipeline_id`` so the frontend can subscribe to
    # the SSE stream immediately.
    #
    # ``is_started`` stays ``False`` on create — the year must NOT be
    # visible to end-users until backoffice confirms every CSV is
    # uploaded and every mandatory module setting is valid.  Operators
    # flip it explicitly via the U5 "Open year for users" button (PATCH
    # ``is_started: true``).  Callers may still override here.
    new_config = YearConfiguration(
        year=year,
        provider=current_user.provider,
        is_started=payload.is_started
        if payload and payload.is_started is not None
        else False,
        config=config_data,
    )
    db.add(new_config)

    snapshot = {
        "provider": current_user.provider.name,
        "is_started": new_config.is_started,
        "config": new_config.config,
    }
    await create_audit_entry(
        db,
        year,
        AuditChangeTypeEnum.CREATE,
        current_user,
        snapshot,
    )

    # Issue #867 — enqueue the unit_sync pipeline tied to this year.  The
    # shape mirrors ``POST /v1/sync/units`` (see
    # ``data_sync.py:sync_units_from_accred``) so the registered
    # ``unit_sync_handler`` reads ``meta.config.target_year`` exactly as
    # it does for the standalone endpoint — the only difference here is
    # that we mint ``pipeline_id`` up-front so we can return it
    # synchronously in the response (the lazy mint inside ``chain_job``
    # would not yield it before the pipeline starts).
    #
    # TODO(#867): if a third caller appears, extract these ~10 lines to
    # ``app/services/`` (or ``app/tasks/_chain.py``) so the endpoint and
    # ``data_sync.sync_units_from_accred`` share one helper.  Until then
    # the duplication is intentional — extraction in flight here would
    # collide with sibling units of issue #867.
    pipeline_id = uuid4()
    job = DataIngestionJob(
        job_type="unit_sync",
        module_type_id=None,
        data_entry_type_id=None,
        year=year,
        ingestion_method=IngestionMethod.api,
        target_type=TargetType.REFERENCE_DATA,
        entity_type=EntityType.GLOBAL_PER_YEAR,
        state=IngestionState.NOT_STARTED,
        provider=current_user.provider,
        pipeline_id=pipeline_id,
        meta={"config": {"target_year": year}},
    )
    # #1236 Phase 2 — Pipeline row MUST exist before the
    # data_ingestion_jobs INSERT flushes, else the FK rejects.
    # ``ensure_pipeline_exists`` is idempotent.
    repo = DataIngestionRepository(db)
    await repo.ensure_pipeline_exists(
        pipeline_id,
        kind="unit_sync",
        entity_type=EntityType.GLOBAL_PER_YEAR.value,
        ingestion_method=IngestionMethod.api.value,
        year=year,
    )
    created_job = await repo.create_ingestion_job(job)

    await db.commit()
    await db.refresh(new_config)

    if created_job.id is None:
        # Defense-in-depth — repository contract returns the persisted row
        # so ``id`` is set after commit.  Surface a 500 rather than firing
        # ``run_job(None)`` if the invariant is violated.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create unit sync job",
        )

    # Fire-and-forget; the safety poller (Plan 310A) recovers the job
    # if this pod crashes before the runner claims it.  Same dispatch
    # path the Plan 310-C unit_sync_handler expects.
    fire_and_forget(
        run_job(created_job.id),
        name=f"run_job-{created_job.id}",
    )

    logger.info(
        f"Year configuration created for year {year}, "
        f"unit_sync pipeline {pipeline_id} enqueued (job_id={created_job.id})",
        extra={
            "user_id": current_user.id,
            "year": year,
            "pipeline_id": str(pipeline_id),
            "job_id": created_job.id,
        },
    )

    # Issue #1215 — freshly-created years have no jobs yet; enrich so the
    # response carries ``incomplete=True`` on every mandatory submodule.
    # Otherwise the frontend reads ``undefined`` → false and the operator
    # sees a deceptively-complete UI before uploading anything.
    enriched_config = copy.deepcopy(new_config.config)
    _enrich_config_with_jobs(enriched_config, {})
    _enrich_config_with_incomplete_flags(enriched_config)
    response = YearConfigurationResponse(
        year=new_config.year,
        is_started=new_config.is_started,
        configuration_completed=new_config.configuration_completed,
        config=enriched_config,
        recalculation_status=[],
        updated_at=new_config.updated_at,
        pipeline_id=str(pipeline_id),
    )
    return response


@router.patch(
    "/{year}",
    response_model=YearConfigurationResponse,
    status_code=status.HTTP_200_OK,
)
async def update_year_configuration(
    year: int,
    payload: YearConfigurationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partially update year configuration.

    Only accessible to super administrators (CO2_SUPERADMIN).
    Validates:
    - reduction_percentage must be between 0 and 1
    - target_year must be > year

    Creates audit entry in audit_documents.

    Args:
        year: Configuration year.
        payload: Update payload.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Updated year configuration.
    """
    if not await is_permitted(current_user, "backoffice.configuration", "edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super administrators can update year configurations",
        )

    # Validate reduction objectives goals if provided
    if payload.config and "reduction_objectives" in payload.config:
        goals = payload.config["reduction_objectives"].get("goals", [])
        for goal in goals:
            if goal.get("target_year", 0) <= year:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"target_year ({goal['target_year']}) must be greater than "
                        f"configuration year ({year})"
                    ),
                )
            reduction_pct = goal.get("reduction_percentage", 0)
            if not (0 <= reduction_pct <= 1):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"reduction_percentage ({reduction_pct}) must be "
                        f"between 0 and 1"
                    ),
                )

    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == current_user.provider,
    )
    result = (await db.exec(stmt)).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No configuration found for year {year}. Use POST to create.",
        )

    # Get old snapshot for audit
    old_snapshot = {
        "provider": current_user.provider.name,
        "is_started": result.is_started,
        "config": result.config,
    }

    if payload.is_started is not None:
        result.is_started = payload.is_started
    if payload.config is not None:
        result.config = _deep_merge(result.config, payload.config)

    db.add(result)

    new_snapshot = {
        "provider": current_user.provider.name,
        "is_started": result.is_started,
        "config": result.config,
    }
    data_diff = {
        k: {"old": old_snapshot[k], "new": new_snapshot[k]}
        for k in old_snapshot
        if old_snapshot[k] != new_snapshot[k]
    }

    await create_audit_entry(
        db,
        year,
        AuditChangeTypeEnum.UPDATE,
        current_user,
        new_snapshot,
        data_diff,
    )

    await db.commit()
    await db.refresh(result)

    logger.info(
        f"Year configuration updated for year {year}",
        extra={"user_id": current_user.id, "year": year},
    )

    repo = DataIngestionRepository(db)
    latest_jobs = await repo.get_latest_jobs_by_year(year)
    job_lookup = _build_job_lookup(latest_jobs)

    enriched_config = copy.deepcopy(result.config)
    _enrich_config_with_jobs(enriched_config, job_lookup)
    _enrich_config_with_incomplete_flags(enriched_config)

    recalc_rows = await repo.get_recalculation_status_by_year(year)
    recalculation_status = _build_recalculation_status(recalc_rows)

    return YearConfigurationResponse(
        year=result.year,
        is_started=result.is_started,
        configuration_completed=result.configuration_completed,
        config=enriched_config,
        recalculation_status=recalculation_status,
        updated_at=result.updated_at,
    )


@router.post(
    "/{year}/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_reduction_objective_file(
    year: int,
    file: UploadFile = File(..., description="File to upload"),
    category: FileCategory = Form(..., description="File category"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload file for reduction objectives.

    Only accessible to super administrators (CO2_SUPERADMIN).
    Categories:
    - footprint: institutional_footprint
    - population: population_projections
    - scenarios: unit_scenarios

    Args:
        year: Configuration year.
        file: Uploaded file.
        category: File category.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        File metadata.
    """
    if not await is_permitted(current_user, "backoffice.configuration", "edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only super administrators can upload files",
        )

    # Validate file extension
    allowed_extensions = {".csv", ".xlsx", ".xls", ".pdf"}
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {allowed_extensions}",
        )

    # Read file content
    content = await file.read()

    # For CSV uploads: validate rows before persisting anything
    parsed_rows: list[dict] | None = None
    if file_ext == ".csv":
        try:
            parsed_rows = validate_reduction_objective_csv(content, category)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"errors": exc.args[0]},
            )

    # Save file (re-wrap content so save_uploaded_file can read() it again)
    file.file = io.BytesIO(content)
    file_metadata = await save_uploaded_file(file, category, year)

    # Map category to config key
    category_map = {
        "footprint": "institutional_footprint",
        "population": "population_projections",
        "scenarios": "unit_scenarios",
    }
    config_key = category_map[category]

    # Update configuration
    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == current_user.provider,
    )
    result = (await db.exec(stmt)).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                f"No configuration found for year {year}. "
                f"Create it first via POST /{year}"
            ),
        )

    # Capture old state for audit diff before any mutation
    old_config = copy.deepcopy(result.config)
    old_snapshot = {
        "provider": current_user.provider.name,
        "is_started": result.is_started,
        "config": old_config,
    }

    # Update file metadata in config
    if "reduction_objectives" not in result.config:
        result.config["reduction_objectives"] = {
            "files": {
                "institutional_footprint": None,
                "population_projections": None,
                "unit_scenarios": None,
            },
            "institutional_footprint": None,
            "population_projections": None,
            "unit_scenarios": None,
            "goals": [],
        }
    else:
        # Ensure the three parsed-data keys exist in case this config was created
        # before the feature was added (old rows won't have them).
        ro = result.config["reduction_objectives"]
        for key in (
            "institutional_footprint",
            "population_projections",
            "unit_scenarios",
        ):
            ro.setdefault(key, None)

    result.config["reduction_objectives"]["files"][config_key] = {
        "path": file_metadata.path,
        "filename": file_metadata.filename,
        "uploaded_at": file_metadata.uploaded_at,
    }

    # If the upload was a CSV, store the parsed rows alongside the metadata
    if parsed_rows is not None:
        result.config["reduction_objectives"][config_key] = parsed_rows

    # Reassign the whole dict so SQLAlchemy detects the change
    result.config = {**result.config}
    db.add(result)

    # Create audit entry with diff
    new_snapshot = {
        "provider": current_user.provider.name,
        "is_started": result.is_started,
        "config": result.config,
    }
    data_diff = {
        k: {"old": old_snapshot[k], "new": new_snapshot[k]}
        for k in old_snapshot
        if old_snapshot[k] != new_snapshot[k]
    }
    await create_audit_entry(
        db,
        year,
        AuditChangeTypeEnum.UPDATE,
        current_user,
        new_snapshot,
        data_diff,
    )

    await db.commit()
    await db.refresh(result)

    logger.info(
        f"File uploaded for year {year}, category {category}",
        extra={
            "user_id": current_user.id,
            "year": year,
            "category": category,
            "uploaded_filename": file_metadata.filename,
        },
    )

    return FileUploadResponse(
        success=True,
        file=file_metadata,
        message="File uploaded successfully",
    )


@router.get(
    "/check-threshold",
    status_code=status.HTTP_200_OK,
)
async def check_emission_threshold(
    year: int,
    module_type_id: int,
    data_entry_type_id: int,
    value: float,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Check if an emission value exceeds the configured threshold.

    Args:
        year: Configuration year.
        module_type_id: Module type ID.
        data_entry_type_id: Data entry type ID.
        value: Emission value to check.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Whether threshold is exceeded and threshold value.
    """
    # Get configuration
    stmt = select(YearConfiguration).where(
        col(YearConfiguration.year) == year,
        col(YearConfiguration.provider) == current_user.provider,
    )
    result = (await db.exec(stmt)).first()

    config = result.config if result else generate_default_year_config()

    try:
        module_type = ModuleTypeEnum(module_type_id)
        data_entry_type = DataEntryTypeEnum(data_entry_type_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid module_type_id or data_entry_type_id: {e}",
        )

    exceeded = check_threshold_exceeded(config, module_type, data_entry_type, value)
    threshold = None

    # Get threshold value for response
    module_config = get_module_config(config, module_type)
    if module_config:
        submodule_config = get_submodule_config(module_config, data_entry_type)
        if submodule_config:
            threshold = submodule_config.get("threshold")

    return {
        "exceeded": exceeded,
        "threshold": threshold,
        "value": value,
    }
