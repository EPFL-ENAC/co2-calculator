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
from app.models.audit import AuditChangeTypeEnum, AuditDocument
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.models.year_configuration import YearConfiguration
from app.repositories.data_ingestion import DataIngestionRepository
from app.schemas.year_configuration import (
    FileCategory,
    FileMetadata,
    FileUploadResponse,
    SyncJobSummary,
    YearConfigurationCreate,
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

logger = get_logger(__name__)
router = APIRouter()


def _build_job_lookup(
    jobs: list,
) -> dict[tuple[int | None, int | None], "SyncJobSummary"]:
    """Build a lookup dict from latest jobs keyed by (module, data_entry) IDs.

    Args:
        jobs: List of DataIngestionJob objects.

    Returns:
        Dict mapping (module_type_id, data_entry_type_id) to SyncJobSummary.
    """
    lookup: dict[tuple[int | None, int | None], SyncJobSummary] = {}
    for job in jobs:
        if job.id is None:
            continue
        key = (job.module_type_id, job.data_entry_type_id)
        lookup[key] = SyncJobSummary(
            job_id=job.id,
            module_type_id=job.module_type_id,
            data_entry_type_id=job.data_entry_type_id,
            year=job.year,
            ingestion_method=job.ingestion_method.value
            if job.ingestion_method is not None
            else 0,
            target_type=job.target_type.value if job.target_type is not None else None,
            state=job.state.value if job.state is not None else None,
            result=job.result.value if job.result is not None else None,
            status_message=job.status_message,
            meta=job.meta,
        )
    return lookup


def _build_jobs_list(jobs: list) -> list["SyncJobSummary"]:
    """Build a flat list of SyncJobSummary from DataIngestionJob objects.

    Args:
        jobs: List of DataIngestionJob objects.

    Returns:
        List of SyncJobSummary (all current jobs for the year).
    """
    result: list[SyncJobSummary] = []
    for job in jobs:
        if job.id is None:
            continue
        result.append(
            SyncJobSummary(
                job_id=job.id,
                module_type_id=job.module_type_id,
                data_entry_type_id=job.data_entry_type_id,
                year=job.year,
                ingestion_method=job.ingestion_method.value
                if job.ingestion_method is not None
                else 0,
                target_type=job.target_type.value
                if job.target_type is not None
                else None,
                state=job.state.value if job.state is not None else None,
                result=job.result.value if job.result is not None else None,
                status_message=job.status_message,
                meta=job.meta,
            )
        )
    return result


def _enrich_config_with_jobs(
    config: dict, job_lookup: dict[tuple[int | None, int | None], SyncJobSummary]
) -> dict:
    """Inject latest_job into each submodule of the config dict.

    Args:
        config: Year configuration dict (modules → submodules).
        job_lookup: Mapping from (module_type_id, data_entry_type_id) to job summary.

    Returns:
        Enriched config dict (mutated in-place for efficiency).
    """
    modules = config.get("modules", {})
    for module_key, module_val in modules.items():
        if not isinstance(module_val, dict):
            continue
        submodules = module_val.get("submodules", {})
        for sub_key, sub_val in submodules.items():
            if not isinstance(sub_val, dict):
                continue
            try:
                m_id = int(module_key)
                s_id = int(sub_key)
            except (ValueError, TypeError):
                continue
            job = job_lookup.get((m_id, s_id))
            sub_val["latest_job"] = job.model_dump() if job else None
    return config


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

    Args:
        session: Database session.
        year: Configuration year.
        change_type: Type of change (CREATE/UPDATE/DELETE).
        user: User making the change.
        data_snapshot: Full configuration snapshot.
        data_diff: Optional diff between old and new config.
    """
    # Calculate hash for integrity chain
    snapshot_str = str(data_snapshot)
    current_hash = hashlib.sha256(snapshot_str.encode()).hexdigest()

    # Get previous version hash if updating
    previous_hash = None
    stmt = (
        select(AuditDocument)
        .where(col(AuditDocument.entity_type) == "year_configuration")
        .where(col(AuditDocument.entity_id) == year)
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
        entity_id=year,
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

    Each submodule in the response includes a `latest_job` field with the most
    recent ingestion job summary. This eliminates the need for a separate
    call to `/sync/jobs/year/{year}/latest`.

    Returns 404 if no configuration has been created yet.
    Backoffice users can then create it via POST /{year}.

    Args:
        year: Configuration year.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Year configuration enriched with latest sync job per submodule.
    """
    stmt = select(YearConfiguration).where(col(YearConfiguration.year) == year)
    result = (await db.exec(stmt)).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No configuration found for year {year}",
        )

    # Fetch latest jobs and enrich config
    repo = DataIngestionRepository(db)
    latest_jobs = await repo.get_latest_jobs_by_year(year)
    job_lookup = _build_job_lookup(latest_jobs)
    jobs_list = _build_jobs_list(latest_jobs)

    enriched_config = copy.deepcopy(result.config)
    _enrich_config_with_jobs(enriched_config, job_lookup)

    return YearConfigurationResponse(
        year=result.year,
        is_started=result.is_started,
        is_reports_synced=result.is_reports_synced,
        config=enriched_config,
        latest_jobs=jobs_list,
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

    Only accessible to backoffice data managers (CO2_BACKOFFICE_METIER).
    Returns 409 if a configuration already exists for the year.

    Args:
        year: Configuration year.
        payload: Optional initial configuration. Defaults to generated config.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Created year configuration.
    """
    if not await is_permitted(current_user, "backoffice.data_management", "edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only backoffice data managers can create year configurations",
        )

    stmt = select(YearConfiguration).where(col(YearConfiguration.year) == year)
    existing = (await db.exec(stmt)).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Configuration for year {year} already exists",
        )

    config_data = (
        payload.config if payload and payload.config else generate_default_year_config()
    )
    new_config = YearConfiguration(
        year=year,
        is_started=payload.is_started
        if payload and payload.is_started is not None
        else False,
        is_reports_synced=payload.is_reports_synced
        if payload and payload.is_reports_synced is not None
        else False,
        config=config_data,
    )
    db.add(new_config)

    snapshot = {
        "is_started": new_config.is_started,
        "is_reports_synced": new_config.is_reports_synced,
        "config": new_config.config,
    }
    await create_audit_entry(
        db,
        year,
        AuditChangeTypeEnum.CREATE,
        current_user,
        snapshot,
    )

    await db.commit()
    await db.refresh(new_config)

    logger.info(
        f"Year configuration created for year {year}",
        extra={"user_id": current_user.id, "year": year},
    )

    return YearConfigurationResponse.model_validate(new_config)


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

    Only accessible to backoffice data managers (CO2_BACKOFFICE_METIER).
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
    if not await is_permitted(current_user, "backoffice.data_management", "edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only backoffice data managers can update year configurations",
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

    stmt = select(YearConfiguration).where(col(YearConfiguration.year) == year)
    result = (await db.exec(stmt)).first()

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No configuration found for year {year}. Use POST to create.",
        )

    # Get old snapshot for audit
    old_snapshot = {
        "is_started": result.is_started,
        "is_reports_synced": result.is_reports_synced,
        "config": result.config,
    }

    if payload.is_started is not None:
        result.is_started = payload.is_started
    if payload.is_reports_synced is not None:
        result.is_reports_synced = payload.is_reports_synced
    if payload.config is not None:
        result.config = _deep_merge(result.config, payload.config)

    db.add(result)

    new_snapshot = {
        "is_started": result.is_started,
        "is_reports_synced": result.is_reports_synced,
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

    # Fetch latest jobs so the response includes them
    repo = DataIngestionRepository(db)
    latest_jobs = await repo.get_latest_jobs_by_year(year)
    jobs_list = _build_jobs_list(latest_jobs)
    job_lookup = _build_job_lookup(latest_jobs)

    enriched_config = copy.deepcopy(result.config)
    _enrich_config_with_jobs(enriched_config, job_lookup)

    return YearConfigurationResponse(
        year=result.year,
        is_started=result.is_started,
        is_reports_synced=result.is_reports_synced,
        config=enriched_config,
        latest_jobs=jobs_list,
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

    Only accessible to backoffice data managers (CO2_BACKOFFICE_METIER).
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
    if not await is_permitted(current_user, "backoffice.data_management", "edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only backoffice data managers can upload files",
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
    stmt = select(YearConfiguration).where(col(YearConfiguration.year) == year)
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
        "is_started": result.is_started,
        "is_reports_synced": result.is_reports_synced,
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
        "is_started": result.is_started,
        "is_reports_synced": result.is_reports_synced,
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
    stmt = select(YearConfiguration).where(col(YearConfiguration.year) == year)
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
