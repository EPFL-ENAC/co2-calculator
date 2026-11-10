"""Temporary uploads live under a folder owned by the uploader."""

import posixpath


def temp_upload_folder(user_id: int | None) -> str:
    return f"tmp/{user_id}"


def owns_temp_upload(file_path: str, user_id: int | None) -> bool:
    """Whether ``file_path`` is inside the user's own temporary folder.

    Normalized first, so ``tmp/1/../2/x`` counts as user 2's file.
    """
    return posixpath.normpath(file_path).startswith(f"{temp_upload_folder(user_id)}/")
