"""Files API endpoints."""

import base64
import datetime
import os
import urllib.parse
from typing import cast

from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from enacit4r_files.services import (
    FileNode,
    FilesStore,
    LocalFilesStore,
    S3FilesStore,
    S3Service,
)
from enacit4r_files.utils.files import FileChecker
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
    status,
)
from opentelemetry import trace
from starlette.datastructures import UploadFile as StarletteUploadFile

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.core.security import is_permitted
from app.models.user import User
from app.utils.permissions import has_permission

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
        # enacit4r_files declares `key: bytes = None` (should be `bytes | None`);
        # the stub is wrong, not this call.
        return S3FilesStore(s3_service, key=encryption_key)  # ty: ignore[invalid-argument-type]
    # Default to local file storage
    return LocalFilesStore(
        settings.FILES_STORAGE_PATH,
        key=encryption_key,  # ty: ignore[invalid-argument-type]
    )


files_store = make_files_store()
file_checker = FileChecker(settings.FILES_MAX_SIZE_MB * 1024 * 1024)

# Upload allowlist. The data-management flows only ingest CSV; the extension
# is the authoritative gate. Extend explicitly when a new import format ships.
ALLOWED_UPLOAD_EXTENSIONS = frozenset({".csv"})
# Browsers label CSV inconsistently (text/csv, the Excel type, or a generic
# octet-stream / empty), so accept the set they actually send. The extension
# check above is what truly constrains the upload.
ALLOWED_UPLOAD_CONTENT_TYPES = frozenset(
    {
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "text/plain",
        "application/octet-stream",
        "",
    }
)
# Content types a browser renders as active content when served inline.
# Serving these from the file store would be stored XSS, so they are always
# forced to download regardless of the requested inline display.
DANGEROUS_INLINE_TYPES = frozenset(
    {
        "text/html",
        "application/xhtml+xml",
        "image/svg+xml",
        "application/xml",
        "text/xml",
        "application/javascript",
        "text/javascript",
    }
)


def validate_upload_mimetype(file: UploadFile) -> None:
    """Reject uploads whose extension or declared content type is not allowed.

    Raises:
        HTTPException: 415 when the file is not an accepted import format.
    """
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Unsupported file type '{ext or file.filename or 'unknown'}'. "
                f"Allowed: {', '.join(sorted(ALLOWED_UPLOAD_EXTENSIONS))}"
            ),
        )
    declared = (file.content_type or "").lower()
    if declared not in ALLOWED_UPLOAD_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported content type '{declared}'",
        )


# upload_temp_files parses the body manually (see docstring) so FastAPI
# never generates a requestBody for it; reproduce the multipart/File schema
# by hand so the OpenAPI contract (and the generated frontend client) don't
# regress.
TEMP_UPLOAD_REQUEST_BODY = {
    "content": {
        "multipart/form-data": {
            "schema": {
                "type": "object",
                "properties": {
                    "files": {
                        "type": "array",
                        "items": {"type": "string", "format": "binary"},
                        "title": "Files",
                    }
                },
                "required": ["files"],
                "title": "Body_upload_temp_files_v1_files_temp_upload_post",
            }
        }
    },
    "required": True,
}


def _require_upload_files(
    raw_files: list[str | StarletteUploadFile],
) -> list[UploadFile]:
    """Narrow parsed multipart 'files' parts to actual file uploads.

    Manual body parsing (needed so auth runs before the body is read, see
    ``upload_temp_files``) skips FastAPI's automatic UploadFile validation,
    so a plain form value sent under the same field name must be rejected
    explicitly instead of crashing downstream on ``.filename``. It also
    means ``request.form()`` hands back Starlette's base ``UploadFile``
    (``fastapi.UploadFile`` is a subclass FastAPI's own validation layer
    would normally construct), so the check narrows against the base class.

    Raises:
        HTTPException: 422 when a 'files' part isn't a file upload.
    """
    for item in raw_files:
        if not isinstance(item, StarletteUploadFile):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="'files' must be file uploads",
            )
    return cast(list[UploadFile], raw_files)


def _record_request_content_length(request: Request) -> None:
    """Attach the declared body size to the current span, when present.

    Lets slow-client-vs-large-file be told apart in traces (#2261);
    best-effort only — a missing or malformed header must not fail the
    upload, it only means the attribute is absent from the trace.
    """
    content_length = request.headers.get("content-length")
    if content_length is None:
        return
    try:
        size = int(content_length)
    except ValueError:
        return
    trace.get_current_span().set_attribute("http.request_content_length", size)


async def _write_temp_files(files: list[UploadFile]) -> list[FileNode]:
    """Validate and write already-parsed uploads to a fresh /tmp folder."""
    if not files:
        raise HTTPException(
            status_code=400, detail="At least one file must be provided"
        )
    for file in files:
        validate_upload_mimetype(file)
    current_time = datetime.datetime.now(datetime.UTC)
    # generate unique name for the files' base folder in S3
    folder_name = str(current_time.timestamp()).replace(".", "")
    folder_path = f"tmp/{folder_name}"
    return [await files_store.write_file(file, folder=folder_path) for file in files]


def build_attachment_disposition(file_path: str) -> str:
    """Build a ``Content-Disposition: attachment`` header for ``file_path``.

    Uses an ASCII ``filename`` fallback plus the RFC 5987 ``filename*`` form so
    the saved name is authoritative across browsers and handles non-ASCII names.
    """
    basename = file_path.rsplit("/", 1)[-1] or "download"
    ascii_basename = basename.encode("ascii", "replace").decode("ascii")
    quoted = urllib.parse.quote(basename, safe="")
    return f"attachment; filename=\"{ascii_basename}\"; filename*=UTF-8''{quoted}"


@router.get(
    "/",
    response_model=list[FileNode],
    response_model_exclude_none=True,
    responses={
        403: {
            "description": "Permission denied",
            "content": {
                "application/json": {
                    "example": {
                        "detail": ("Permission denied: backoffice.configuration.view")
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
    current_user: User = Depends(get_current_user),
):
    """List files in the specified directory.

    **Required Permission**: `backoffice.configuration.view`

    **Authorization**:
    - Backoffice metier: Can list all data management files
    - Other users: No access

    This endpoint lists files stored in the file storage (local or S3)
    for data management purposes (CSV uploads, sync files, etc.).

    Raises:
        403: Missing required permission
        400: Invalid file path
    """
    if not await is_permitted(current_user, "backoffice.configuration", "view"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: requires backoffice.configuration.view",
        )

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
                        "detail": ("Permission denied: backoffice.configuration.view")
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
    current_user: User = Depends(get_current_user),
):
    """Retrieve a file from file storage.

    **Required Permission**: `backoffice.configuration.view`

    **Authorization**:
    - Backoffice metier: Can access all data management files
    - Other users: No access

    Raises:
        403: Missing required permission
        404: File not found
        400: Invalid file path
        500: Internal server error
    """
    if not await is_permitted(current_user, "backoffice.configuration", "view"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: requires backoffice.configuration.view",
        )

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
            media_type = content_type or "application/octet-stream"
            # ``nosniff`` stops the browser from second-guessing our
            # Content-Type (e.g. sniffing a malformed CSV as HTML and
            # running script injection on a malformed row).
            headers = {"X-Content-Type-Options": "nosniff"}
            # Force a real download when explicitly requested OR when the
            # stored type would execute inline (html/svg/xml/js) — serving
            # those inline from the file store would be stored XSS. Without
            # ``Content-Disposition: attachment`` Safari/Firefox also ignore
            # the client ``<a download>`` and strip the extension (regression
            # 2026-05-21: ``equipments_data.csv`` saved as ``equipments_data``).
            base_type = media_type.split(";", 1)[0].strip().lower()
            if download or base_type in DANGEROUS_INLINE_TYPES:
                headers["Content-Disposition"] = build_attachment_disposition(file_path)
            return Response(content=body, media_type=media_type, headers=headers)
        else:
            raise HTTPException(status_code=404, detail="File not found")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        logger.error(f"Error retrieving file: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post(
    "/temp-upload",
    status_code=200,
    response_model=list[FileNode],
    response_model_exclude_none=True,
    description="Upload any assets to file storage in the /tmp folder",
    openapi_extra={"requestBody": TEMP_UPLOAD_REQUEST_BODY},
)
async def upload_temp_files(
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Upload files to the /tmp folder in the file storage.

    **Required Permission**: `backoffice.configuration.edit`

    Used for temporary file uploads before processing (e.g., CSV imports).

    Takes the raw ``Request`` instead of a typed ``UploadFile`` body param
    and parses the multipart body only after the permission check below.
    FastAPI/Starlette otherwise read the *entire* body unconditionally
    before resolving any dependency the moment a route declares a
    File/Form param (``fastapi/routing.py``: ``body = await request.form()``
    runs ahead of ``solve_dependencies()``), which let an unauthenticated
    caller push an arbitrary payload through before being rejected (#2261).
    """
    perms = current_user.calculate_permissions()
    can_upload = has_permission(perms, "backoffice.configuration", "edit") or any(
        isinstance(actions, list) and "sync" in actions
        for key, actions in perms.items()
        if key.startswith("modules.")
    )
    if not can_upload:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Permission denied: requires backoffice.configuration.edit"
                " or module sync access"
            ),
        )

    _record_request_content_length(request)
    async with request.form() as form:
        files = _require_upload_files(form.getlist("files"))
        await file_checker.check_size(files)
        logger.info(
            "File upload to /tmp requested",
            extra={"user_id": current_user.id, "file_count": len(files)},
        )
        return await _write_temp_files(files)


@router.delete(
    "/{file_path:path}",
    status_code=204,
    description="Delete asset present in the file storage if it is in /tmp/ folder",
)
async def delete_temp_files(
    file_path: str,
    current_user: User = Depends(get_current_user),
):
    """Delete files from the /tmp folder.

    **Required Permission**: `backoffice.configuration.edit`

    Only files in /tmp/ folder can be deleted.
    """
    if not await is_permitted(current_user, "backoffice.configuration", "edit"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: requires backoffice.configuration.edit",
        )

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
