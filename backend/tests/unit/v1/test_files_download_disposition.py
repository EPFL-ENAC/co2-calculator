"""Regression tests for ``GET /api/v1/files/{path}?d=true``.

User-reported (Guilbert, 2026-05-21): clicking "download last CSV" on
the data-management page saved the file as ``equipments_data``
(no extension) instead of ``equipments_data.csv``.

Root cause: the endpoint returned the file body without a
``Content-Disposition`` header. With Safari (and to a lesser extent
Firefox), the ``<a download="…">`` attribute on the client side is
ignored when the response carries no ``attachment`` disposition; the
browser then falls back to sniffing the Content-Type and strips the
URL extension when the sniff disagrees.

Fix: when ``download=True``, set
``Content-Disposition: attachment; filename="<basename>";
filename*=UTF-8''<percent-encoded>`` so the saved filename is
authoritative regardless of browser quirks.  Also set ``media_type``
explicitly on both branches so the inline path doesn't fall back to
an unset Content-Type (which trips MIME-sniffing on some browsers).

These tests pin:
1. ``?d=true`` produces ``Content-Disposition: attachment`` with the
   path's basename (the load-bearing fix).
2. Without ``?d=true`` no disposition is set (inline branch stays
   inline — preserves the image-preview use case).
3. Non-ASCII filenames use the RFC 5987 ``filename*`` form alongside
   an ASCII fallback so older clients still get something readable.
4. ``Content-Type`` is set explicitly on both branches (defends
   against MIME-sniffing for malformed CSVs).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import files as files_module
from app.main import app
from app.models.user import User


@pytest.fixture
def client():
    """Test client for HTTP requests."""
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "operator@test.example"
    user.institutional_id = "TEST"
    return user


@pytest.fixture(autouse=True)
def _allow_permissions():
    """Bypass the auth + permission gate; this suite tests download
    semantics, not the perm path (covered by other suites)."""
    from app.api.deps import get_current_user

    fake = MagicMock(spec=User)
    fake.id = 1
    fake.email = "operator@test.example"
    fake.institutional_id = "TEST"
    app.dependency_overrides[get_current_user] = lambda: fake

    async def _allow(*_args, **_kwargs):
        return True

    with patch.object(files_module, "is_permitted", new=_allow):
        yield
    app.dependency_overrides.clear()


def _patch_files_store(content: bytes, content_type: str | None):
    """Return a patch context that replaces ``files_store.get_file``
    with an AsyncMock returning the given body + type."""
    return patch.object(
        files_module.files_store,
        "get_file",
        new=AsyncMock(return_value=(content, content_type)),
    )


def test_download_sets_content_disposition_attachment_with_filename(client):
    """The load-bearing assertion: ?d=true MUST set
    Content-Disposition: attachment with the path's basename, so the
    browser saves the file with the right name regardless of its
    ``<a download>`` quirks."""
    csv_body = b"col1,col2\n1,2\n"
    with _patch_files_store(csv_body, "text/csv"):
        resp = client.get("/api/v1/files/processed/152/equipments_data.csv?d=true")

    assert resp.status_code == 200, resp.text
    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" in disposition, disposition
    # ASCII fallback for old clients.
    assert 'filename="equipments_data.csv"' in disposition, disposition
    # RFC 5987 form for full-fidelity Unicode.
    assert "filename*=UTF-8''equipments_data.csv" in disposition, disposition
    # Content-Type stays authoritative — Safari uses it as one of the
    # signals to decide whether to honor ``<a download>``.
    assert resp.headers["content-type"].startswith("text/csv"), resp.headers
    assert resp.content == csv_body


def test_inline_branch_omits_disposition_but_sets_content_type(client):
    """Without ?d=true the response should NOT set ``attachment`` —
    this branch backs the image-preview use case where the browser
    renders the file inline.  But it MUST set Content-Type so
    browsers don't MIME-sniff a malformed CSV as HTML and run script
    injection."""
    with _patch_files_store(b"\x89PNG fake", "image/png"):
        resp = client.get("/api/v1/files/processed/152/preview.png")

    assert resp.status_code == 200, resp.text
    disposition = resp.headers.get("content-disposition", "")
    assert "attachment" not in disposition
    assert resp.headers["content-type"].startswith("image/png"), resp.headers


def test_download_handles_unknown_content_type(client):
    """When ``mimetypes.guess_type`` returns None (extensionless or
    unknown file), the response still serves the bytes with an
    explicit ``application/octet-stream`` Content-Type — never an
    unset one (which trips MIME-sniffing).
    """
    with _patch_files_store(b"raw bytes", None):
        resp = client.get("/api/v1/files/processed/152/no_extension?d=true")

    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == "application/octet-stream"
    disposition = resp.headers["content-disposition"]
    assert 'filename="no_extension"' in disposition


def test_download_encodes_non_ascii_filename(client):
    """Non-ASCII characters in the filename are percent-encoded in
    the RFC 5987 ``filename*`` form; the ASCII fallback gets ``?`` for
    non-representable chars (Python's ``encode('ascii', 'replace')``).
    Old clients that don't understand ``filename*`` still see a sane
    string."""
    with _patch_files_store(b"x", "text/csv"):
        resp = client.get("/api/v1/files/processed/152/équipements.csv?d=true")

    assert resp.status_code == 200, resp.text
    disposition = resp.headers["content-disposition"]
    # RFC 5987 percent-encoded form — preserves the accented char.
    assert "%C3%A9quipements.csv" in disposition, disposition
    # ASCII fallback — ``é`` becomes ``?``.
    assert 'filename="?quipements.csv"' in disposition, disposition
