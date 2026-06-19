"""Security tests for the files API: upload MIME validation and safe
download Content-Disposition / MIME-sniffing handling.

Covers two hardening measures:

1. ``POST /temp-upload`` rejects anything that is not an allowed import
   format (CSV) with ``415`` — the extension is the authoritative gate,
   the declared content type is a secondary check.
2. ``GET /{path}`` always sends ``X-Content-Type-Options: nosniff`` and
   forces ``Content-Disposition: attachment`` for content types that a
   browser would execute inline (html/svg/xml/js) even when inline
   display was requested — defends against stored XSS via the file store.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from enacit4r_files.services import FileNode
from fastapi.testclient import TestClient

from app.api.v1 import files as files_module
from app.main import app
from app.models.user import User


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _allow_permissions():
    """Bypass auth + permission gates; these tests exercise upload
    validation and download MIME handling, not the perm path."""
    from app.api.deps import get_current_user

    fake = MagicMock(spec=User)
    fake.id = 1
    fake.email = "operator@test.example"
    fake.institutional_id = "TEST"
    # upload_temp_files gates on calculate_permissions(); grant edit.
    fake.calculate_permissions.return_value = {
        "backoffice.configuration": ["edit"],
    }
    app.dependency_overrides[get_current_user] = lambda: fake

    async def _allow(*_args, **_kwargs):
        return True

    with patch.object(files_module, "is_permitted", new=_allow):
        yield
    app.dependency_overrides.clear()


def _patch_get_file(content: bytes, content_type: str | None):
    return patch.object(
        files_module.files_store,
        "get_file",
        new=AsyncMock(return_value=(content, content_type)),
    )


# --- Upload MIME validation -------------------------------------------------


def test_upload_rejects_non_csv_extension(client):
    """An executable/script disguised by extension is rejected with 415
    before it ever reaches storage."""
    with patch.object(files_module.files_store, "write_file", new=AsyncMock()) as write:
        resp = client.post(
            "/api/v1/files/temp-upload",
            files={
                "files": ("payload.html", b"<script>alert(1)</script>", "text/html")
            },
        )
    assert resp.status_code == 415, resp.text
    write.assert_not_called()


def test_upload_rejects_csv_extension_with_dangerous_content_type(client):
    """Extension passes but a script content type does not — both must be
    acceptable."""
    with patch.object(files_module.files_store, "write_file", new=AsyncMock()) as write:
        resp = client.post(
            "/api/v1/files/temp-upload",
            files={"files": ("data.csv", b"col1,col2\n1,2\n", "text/html")},
        )
    assert resp.status_code == 415, resp.text
    write.assert_not_called()


def test_upload_accepts_csv(client):
    """A legitimate CSV upload is written to storage."""
    node = FileNode(name="data.csv", is_file=True)
    with patch.object(
        files_module.files_store,
        "write_file",
        new=AsyncMock(return_value=node),
    ) as write:
        resp = client.post(
            "/api/v1/files/temp-upload",
            files={"files": ("data.csv", b"col1,col2\n1,2\n", "text/csv")},
        )
    assert resp.status_code == 200, resp.text
    write.assert_called_once()


def test_upload_accepts_csv_with_generic_octet_stream(client):
    """Browsers sometimes send application/octet-stream for CSV; the
    extension is authoritative so this is accepted."""
    with patch.object(
        files_module.files_store,
        "write_file",
        new=AsyncMock(return_value=FileNode(name="data.csv", is_file=True)),
    ) as write:
        resp = client.post(
            "/api/v1/files/temp-upload",
            files={
                "files": ("data.csv", b"col1,col2\n1,2\n", "application/octet-stream")
            },
        )
    assert resp.status_code == 200, resp.text
    write.assert_called_once()


# --- Download MIME-sniffing / disposition hardening -------------------------


def test_download_sets_nosniff_on_inline_branch(client):
    """Inline responses carry X-Content-Type-Options: nosniff."""
    with _patch_get_file(b"\x89PNG fake", "image/png"):
        resp = client.get("/api/v1/files/processed/152/preview.png")
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_download_sets_nosniff_on_attachment_branch(client):
    """Explicit downloads carry nosniff too."""
    with _patch_get_file(b"col1,col2\n1,2\n", "text/csv"):
        resp = client.get("/api/v1/files/processed/152/data.csv?d=true")
    assert resp.status_code == 200, resp.text
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_html_file_is_forced_to_attachment_even_inline(client):
    """A stored HTML file requested for inline display is forced to
    download — never rendered — so it cannot run as stored XSS."""
    with _patch_get_file(b"<script>alert(1)</script>", "text/html"):
        resp = client.get("/api/v1/files/processed/152/evil.html")
    assert resp.status_code == 200, resp.text
    assert "attachment" in resp.headers.get("content-disposition", "")
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_svg_file_is_forced_to_attachment_even_inline(client):
    """SVG can carry inline script; it is forced to download as well."""
    with _patch_get_file(b"<svg onload=alert(1)>", "image/svg+xml"):
        resp = client.get("/api/v1/files/processed/152/evil.svg")
    assert resp.status_code == 200, resp.text
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_safe_image_stays_inline(client):
    """A genuine image preview is still served inline (no attachment)."""
    with _patch_get_file(b"\x89PNG fake", "image/png"):
        resp = client.get("/api/v1/files/processed/152/preview.png")
    assert resp.status_code == 200, resp.text
    assert "attachment" not in resp.headers.get("content-disposition", "")
