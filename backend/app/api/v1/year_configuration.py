"""Year configuration API endpoints."""

import hashlib
import os
from datetime import datetime
from typing import Any, Dict
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    UploadFile,
    status,
)
from sqlmodel import Session, col, select

from app.api.deps import get_current_user, get_db
from app.core.logging import get_logger
from app.models.audit import AuditChangeTypeEnum, AuditDocument
from app.models.data_entry import DataEntryTypeEnum
from app.models.module_type import ModuleTypeEnum
from app.models.user import User
from app.models.year_configuration import YearConfiguration
from app.schemas.year_configuration import (
    FileCategory,
    FileMetadata,
    FileUploadResponse,
    YearConfigurationResponse,
    YearConfigurationUpdate,
)
from app.services.year_config_service import (
    check_threshold_exceeded,
    generate_default_year_config,
    get_module_config,
    get_submodule_config,
)

logger = get_logger(__name__)
router = APIRouter()


def get_files_storage_path() -> str:
    """Get the files storage path from environment or default."""
    return os.environ.get("FILES_STORAGE_PATH", "./files_storage")


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename preserving extension."""
    name, ext = os.path.splitext(original_filename)
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
    storage_path = get_files_storage_path()
    category_dir = f"reduction_objectives/{category}"
    full_path = os.path.join(storage_path, category_dir)

    # Create directory if it doesn't exist
    os.makedirs(full_path, exist_ok=True)

    # Generate unique filename
    unique_filename = generate_unique_filename(file.filename or "uploaded_file")
    file_path = os.path.join(full_path, unique_filename)

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
    session: Session,
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
    result = session.exec(stmt).first()

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
        ip_address="127.0.0.1",  # TODO: Get from request
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
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Fetch year configuration.

    If no configuration exists for the year, returns a default configuration
    generated from ModuleTypeEnum and MODULE_TYPE_TO_DATA_ENTRY_TYPES.

    Args:
        year: Configuration year.
        db: Database session.
        current_user: Current authenticated user.

    Returns:
        Year configuration.
    """
    # Try to find existing configuration
    stmt = select(YearConfiguration).where(col(YearConfiguration.year) == year)
    result = db.exec(stmt).first()

    if result:
        return YearConfigurationResponse.model_validate(result)

    # Return default configuration (don't create in DB - manual only per PRD)
    default_config = generate_default_year_config()
    return YearConfigurationResponse(
        year=year,
        is_started=False,
        is_reports_synced=False,
        config=default_config,
        updated_at=datetime.utcnow(),
    )


@router.patch(
    "/{year}",
    response_model=YearConfigurationResponse,
    status_code=status.HTTP_200_OK,
)
async def update_year_configuration(
    year: int,
    payload: YearConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Partially update year configuration.

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

    # Get existing configuration or create new
    stmt = select(YearConfiguration).where(col(YearConfiguration.year) == year)
    result = db.exec(stmt).first()

    if result:
        # Get old snapshot for audit
        old_snapshot = {
            "is_started": result.is_started,
            "is_reports_synced": result.is_reports_synced,
            "config": result.config,
        }

        # Update fields
        if payload.is_started is not None:
            result.is_started = payload.is_started
        if payload.is_reports_synced is not None:
            result.is_reports_synced = payload.is_reports_synced
        if payload.config is not None:
            result.config = payload.config

        # Create audit diff
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

        # Create audit entry
        await create_audit_entry(
            db,
            year,
            AuditChangeTypeEnum.UPDATE,
            current_user,
            new_snapshot,
            data_diff,
        )

        logger.info(
            f"Year configuration updated for year {year}",
            extra={"user_id": current_user.id, "year": year},
        )
    else:
        # Create new configuration
        if (
            payload.is_started is None
            and payload.is_reports_synced is None
            and payload.config is None
        ):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No configuration found for year {year}. Use POST to create.",
            )

        config_data = (
            payload.config if payload.config else generate_default_year_config()
        )
        new_config = YearConfiguration(
            year=year,
            is_started=payload.is_started or False,
            is_reports_synced=payload.is_reports_synced or False,
            config=config_data,
        )
        db.add(new_config)

        # Create audit entry
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

        logger.info(
            f"Year configuration created for year {year}",
            extra={"user_id": current_user.id, "year": year},
        )
        result = new_config

    db.commit()
    db.refresh(result)

    return YearConfigurationResponse.model_validate(result)


@router.post(
    "/{year}/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_200_OK,
)
async def upload_reduction_objective_file(
    year: int,
    file: UploadFile = File(..., description="File to upload"),
    category: FileCategory = File(..., description="File category"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload file for reduction objectives.

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
    # Validate file extension
    allowed_extensions = {".csv", ".xlsx", ".xls", ".pdf"}
    file_ext = os.path.splitext(file.filename or "")[1].lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type not allowed. Allowed: {allowed_extensions}",
        )

    # Save file
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
    result = db.exec(stmt).first()

    if not result:
        # Create default config first
        result = YearConfiguration(
            year=year,
            is_started=False,
            is_reports_synced=False,
            config=generate_default_year_config(),
        )
        db.add(result)
        db.flush()

    # Update file metadata in config
    if "reduction_objectives" not in result.config:
        result.config["reduction_objectives"] = {
            "files": {
                "institutional_footprint": None,
                "population_projections": None,
                "unit_scenarios": None,
            },
            "goals": [],
        }

    result.config["reduction_objectives"]["files"][config_key] = {
        "path": file_metadata.path,
        "filename": file_metadata.filename,
        "uploaded_at": file_metadata.uploaded_at,
    }

    # Create audit entry
    snapshot = {
        "is_started": result.is_started,
        "is_reports_synced": result.is_reports_synced,
        "config": result.config,
    }
    await create_audit_entry(
        db,
        year,
        AuditChangeTypeEnum.UPDATE,
        current_user,
        snapshot,
    )

    db.commit()
    db.refresh(result)

    logger.info(
        f"File uploaded for year {year}, category {category}",
        extra={
            "user_id": current_user.id,
            "year": year,
            "category": category,
            "filename": file_metadata.filename,
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
    db: Session = Depends(get_db),
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
    result = db.exec(stmt).first()

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
