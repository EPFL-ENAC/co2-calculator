"""Files API endpoints."""

import base64
import datetime
from typing import List

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from enacit4r_files.services import (
    FileNode,
    FilesStore,
    LocalFilesStore,
    S3FilesStore,
    S3Service,
)
from enacit4r_files.utils.files import FileChecker
from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile

from app.api.deps import get_current_active_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import require_permission
from app.models.user import User

logger = get_logger(__name__)
router = APIRouter()
settings = get_settings()


def make_files_store() -> FilesStore:
    """Create and return a FilesStore instance.

    Returns:
        FilesStore: An instance of FilesStore for the configured file storage.
    """
    encryption_key = None  # Set to None or provide your encryption key here
    if settings.FILES_ENCRYPTION_KEY and settings.FILES_ENCRYPTION_SALT:
        # Derive a key from the provided encryption key and salt
        kdf = Scrypt(
            salt=settings.FILES_ENCRYPTION_SALT.encode(),
            length=32,
            n=2**14,
            r=8,
            p=1,
        )
        encryption_key = base64.urlsafe_b64encode(
            kdf.derive(settings.FILES_ENCRYPTION_KEY.encode())
        )
    # Use S3 storage if configured
    if (
        settings.S3_ENDPOINT_HOSTNAME
        and settings.S3_ACCESS_KEY_ID
        and settings.S3_SECRET_ACCESS_KEY
    ):
        s3_service = S3Service(
            s3_endpoint_url=f"{settings.S3_ENDPOINT_PROTOCOL}://{settings.S3_ENDPOINT_HOSTNAME}",
            s3_access_key_id=settings.S3_ACCESS_KEY_ID,
            s3_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region=settings.S3_REGION,
            bucket=settings.S3_BUCKET,
            path_prefix=settings.S3_PATH_PREFIX,
        )
        return S3FilesStore(s3_service, key=encryption_key)
    # Default to local file storage
    return LocalFilesStore(settings.FILES_STORAGE_PATH, key=encryption_key)


files_store = make_files_store()
file_checker = FileChecker(settings.FILES_MAX_SIZE_MB * 1024 * 1024)


@router.get(
    "/",
    response_model=List[FileNode],
    response_model_exclude_none=True,
    responses={
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Permission denied: backoffice.files.view required"
                    }
                }
            },
        },
        400: {
            "description": "Invalid file path",
            "content": {
                "application/json": {"example": {"detail": "Invalid file path"}}
            },
        },
    },
)
async def list_files(
    path: str = Query("", description="Path to list files from"),
    recursive: bool = Query(False, description="List files recursively"),
    current_user: User = Depends(require_permission("backoffice.files", "view")),
):
    """
    List files in the specified directory.

    **Required Permission**: `backoffice.files.view`

    **Authorization**:
    - Backoffice admin: Can list all files
    - Backoffice std: Can list all files
    - Other users: No access

    This endpoint lists files stored in the file storage (local or S3).

    Raises:
        403: Missing required permission
        400: Invalid file path
    """
    logger.info(
        "File list requested",
        extra={"user_id": current_user.id, "path": path},
    )
    try:
        path = files_store.sanitize_path(path)
    except ValueError as e:
        logger.error(f"Invalid file path for listing '{path}': {e}")
        raise HTTPException(status_code=400, detail="Invalid file path")

    files = await files_store.list_files(path, recursive=recursive)
    return files


@router.get(
    "/{file_path:path}",
    status_code=200,
    description="Download any assets from file storage",
    responses={
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Permission denied: backoffice.files.view required"
                    }
                }
            },
        },
        404: {
            "description": "File not found",
            "content": {"application/json": {"example": {"detail": "File not found"}}},
        },
        400: {
            "description": "Invalid file path",
            "content": {
                "application/json": {"example": {"detail": "Invalid file path"}}
            },
        },
    },
)
async def get_file(
    file_path: str,
    download: bool = Query(
        False, alias="d", description="Download file instead of inline display"
    ),
    current_user: User = Depends(require_permission("backoffice.files", "view")),
):
    """
    Retrieve a file from file storage.

    **Required Permission**: `backoffice.files.view`

    **Authorization**:
    - Backoffice admin: Can access all files
    - Backoffice std: Can access all files
    - Other users: No access

    Raises:
        403: Missing required permission
        404: File not found
        400: Invalid file path
        500: Internal server error
    """
    logger.info(
        "File requested",
        extra={
            "user_id": current_user.id,
            "file_path": file_path,
            "download": download,
        },
    )
    try:
        file_path = files_store.sanitize_path(file_path)
    except ValueError as e:
        logger.error(f"Invalid file path for retrieval '{file_path}': {e}")
        raise HTTPException(status_code=400, detail="Invalid file path")

    try:
        (body, content_type) = await files_store.get_file(file_path)
        if body:
            if download:
                # download file
                return Response(content=body, media_type=content_type)
            else:
                # inline image
                return Response(content=body)
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Error retrieving file: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/tmp",
    status_code=200,
    response_model=List[FileNode],
    response_model_exclude_none=True,
    description="Upload any assets to file storage in the /tmp folder",
    dependencies=[Depends(file_checker.check_size)],
)
async def upload_temp_files(
    files: list[UploadFile] = File(description="Multiple file upload"),
    current_user: User = Depends(get_current_active_user),
):
    """
    Upload files to the /tmp folder in the file storage.
    """
    logger.info(
        "File upload to /tmp requested",
        extra={"user_id": current_user.id, "file_count": len(files)},
    )
    if not files:
        raise HTTPException(
            status_code=400, detail="At least one file must be provided"
        )
    current_time = datetime.datetime.now(datetime.timezone.utc)
    # generate unique name for the files' base folder in S3
    folder_name = str(current_time.timestamp()).replace(".", "")
    folder_path = f"tmp/{folder_name}"
    children = [
        await files_store.write_file(file, folder=folder_path) for file in files
    ]
    return children


@router.delete(
    "/{file_path:path}",
    status_code=204,
    description="Delete asset present in the file storage if it is in /tmp/ folder",
)
async def delete_temp_files(
    file_path: str, current_user: User = Depends(get_current_active_user)
):
    logger.info(
        "File deletion from /tmp requested",
        extra={"user_id": current_user.id, "file_path": file_path},
    )
    try:
        file_path = files_store.sanitize_path(file_path)
    except ValueError as e:
        logger.error(f"Invalid file path for deletion '{file_path}': {e}")
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not file_path.startswith("tmp/"):
        raise HTTPException(
            status_code=403, detail="Can only delete files in /tmp/ folder"
        )
    # delete file at path
    await files_store.delete_file(file_path)
    return
