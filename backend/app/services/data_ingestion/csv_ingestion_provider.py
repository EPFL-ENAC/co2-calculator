"""Shared staging step for CSV-based ingestion providers.

Split out as its own intermediate class rather than added to
``DataIngestionProvider`` (in ``base_provider.py``) because that base also
backs non-file, API-based providers — ``factor_update_provider.py`` and
``api_providers/base_tableau_api_provider.py`` — which have no file path
and no reason to carry CSV-staging surface.

Every CSV provider (``BaseCSVProvider``, ``BaseFactorCSVProvider``,
``BaseReductionObjectiveCSVProvider``, ``ReferenceDataCSVProvider``) used to
duplicate this move+download+decode block instead of sharing it, which is
exactly how the BOM decode fix (#6523) landed on one provider and silently
never reached its siblings.
"""

from abc import ABC

from app.core.logging import get_logger
from app.services.data_ingestion.base_provider import DataIngestionProvider

logger = get_logger(__name__)


def _validate_file_path(file_path: str) -> None:
    """Validate file_path to prevent directory traversal attacks.
    File should come from files_store and start with expected prefixes.
    """
    if not file_path:
        raise ValueError("file_path cannot be empty")

    # Prevent directory traversal
    if ".." in file_path:
        raise ValueError("Invalid file_path: directory traversal not allowed")

    # Normalize path and check for absolute paths
    if file_path.startswith("/"):
        raise ValueError("Invalid file_path: absolute paths not allowed")

    # Only allow files from tmp/ or similar temporary upload directories
    allowed_prefixes = ("tmp/", "uploads/", "temporary/")
    if not any(file_path.startswith(prefix) for prefix in allowed_prefixes):
        raise ValueError(
            f"Invalid file_path: must start with one of {allowed_prefixes}"
        )


class CSVIngestionProvider(DataIngestionProvider, ABC):
    """Common base for providers that stage an uploaded CSV before parsing."""

    async def _download_and_decode_csv(
        self, tmp_path: str | None
    ) -> tuple[str, str, str]:
        """Move an uploaded CSV from ``tmp/`` to ``processing/`` and decode it.

        ``utf-8-sig`` strips a leading BOM if present (Excel/Windows exports
        commonly add one) and is a no-op otherwise. A raw ``"utf-8"`` decode
        instead leaves the BOM glued onto the first header cell, which
        silently breaks a plain column-name lookup (#6523).

        Returns ``(csv_text, processing_path, filename)``.
        """
        if not tmp_path:
            raise ValueError("Missing file_path in config")
        _validate_file_path(tmp_path)
        processing_path = await self._move_to_processing(tmp_path)
        filename = processing_path.split("/")[-1]

        logger.info(f"Downloading CSV from {processing_path}")
        file_content, _ = await self.files_store.get_file(processing_path)
        csv_text = file_content.decode("utf-8-sig")
        return csv_text, processing_path, filename
