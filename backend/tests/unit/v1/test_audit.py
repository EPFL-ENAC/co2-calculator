from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.v1 import audit
from app.main import app
from app.models.audit import AuditChangeTypeEnum, AuditDocument
from app.models.user import User

app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def client():
    """Test client for making HTTP requests."""
    with TestClient(app) as c:
        yield c
    # Clear overrides after each test
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user():
    """Mock user for authentication."""
    user = MagicMock(spec=User)
    user.id = 1
    user.email = "test@example.com"
    user.provider_code = "provider-123"
    user.display_name = "Test User"
    user.roles = []
    return user


@pytest.fixture
def mock_audit_doc():
    """Create a mock audit document with all fields populated."""
    doc = MagicMock(spec=AuditDocument)
    doc.id = 1
    doc.entity_type = "test_entity"
    doc.entity_id = 123
    doc.version = 1
    doc.change_type = AuditChangeTypeEnum.CREATE
    doc.change_reason = "Test reason"
    doc.changed_by = 1
    doc.changed_at = datetime(2024, 1, 15, 10, 30, 0)
    doc.handler_id = "handler-123"
    doc.handled_ids = ["handler-123"]
    doc.ip_address = "127.0.0.1"
    doc.route_path = "/api/test"
    doc.data_snapshot = {"key": "value"}
    doc.sync_status = "PENDING"
    doc.sync_error = None
    doc.synced_at = None
    doc.data_diff = None

    # Mock the model_dump method to return fields as they would be serialized
    def mock_model_dump():
        return {
            "id": doc.id,
            "entity_type": doc.entity_type,
            "entity_id": doc.entity_id,
            "version": doc.version,
            "change_type": doc.change_type,
            "change_reason": doc.change_reason,
            "changed_by": doc.changed_by,
            "changed_at": doc.changed_at,
            "handler_id": doc.handler_id,
            "handled_ids": doc.handled_ids or [],
            "ip_address": doc.ip_address,
            "route_path": doc.route_path,
            "data_snapshot": doc.data_snapshot,
            "sync_status": doc.sync_status,
            "sync_error": doc.sync_error,
            "synced_at": doc.synced_at,
            "data_diff": doc.data_diff,
        }

    doc.model_dump = mock_model_dump
    return doc


@pytest.fixture
def mock_audit_doc_with_none_handled_ids():
    """Create a mock audit document with handled_ids set to None."""
    doc = MagicMock(spec=AuditDocument)
    doc.id = 1
    doc.entity_type = "test_entity"
    doc.entity_id = 123
    doc.version = 1
    doc.change_type = AuditChangeTypeEnum.CREATE
    doc.change_reason = "Test reason"
    doc.changed_by = 1
    doc.changed_at = datetime(2024, 1, 15, 10, 30, 0)
    doc.handler_id = "handler-123"
    doc.handled_ids = None  # This is the key difference
    doc.ip_address = "127.0.0.1"
    doc.route_path = "/api/test"
    doc.data_snapshot = {"key": "value"}
    doc.sync_status = "PENDING"
    doc.sync_error = None
    doc.synced_at = None
    doc.data_diff = None

    # Mock the model_dump method to return fields as they would be serialized
    def mock_model_dump():
        return {
            "id": doc.id,
            "entity_type": doc.entity_type,
            "entity_id": doc.entity_id,
            "version": doc.version,
            "change_type": doc.change_type,
            "change_reason": doc.change_reason,
            "changed_by": doc.changed_by,
            "changed_at": doc.changed_at,
            "handler_id": doc.handler_id,
            "handled_ids": doc.handled_ids or [],
            "ip_address": doc.ip_address,
            "route_path": doc.route_path,
            "data_snapshot": doc.data_snapshot,
            "sync_status": doc.sync_status,
            "sync_error": doc.sync_error,
            "synced_at": doc.synced_at,
            "data_diff": doc.data_diff,
        }

    doc.model_dump = mock_model_dump
    return doc


@pytest.fixture
def mock_db_session():
    """Mock database session."""
    mock_session = AsyncMock(spec=AsyncSession)

    # Mock exec for User display name queries
    result_mock = MagicMock()
    result_mock.all.return_value = []
    mock_session.exec = AsyncMock(return_value=result_mock)

    return mock_session


@pytest.fixture
def mock_audit_repo():
    """Mock audit repository."""
    from app.repositories.audit_repo import AuditDocumentRepository

    return AsyncMock(spec=AuditDocumentRepository)


@pytest.fixture
def mock_auth_allow(monkeypatch):
    """Mock authentication to allow access."""

    async def mock_query_policy(*args, **kwargs):
        return {"allow": True}

    monkeypatch.setattr("app.core.security.query_policy", mock_query_policy)


@pytest.fixture
def mock_auth_deny(monkeypatch):
    """Mock authentication to deny access."""

    async def mock_query_policy(*args, **kwargs):
        return {"allow": False}

    monkeypatch.setattr("app.core.security.query_policy", mock_query_policy)


# ============================================================================
# HELPER FUNCTION TESTS
# ============================================================================


class TestFetchUserDisplayNames:
    """Tests for _fetch_user_display_names helper function."""

    @pytest.mark.asyncio
    async def test_empty_provider_codes(self, mock_db_session):
        """Empty provider codes list returns empty dict."""
        result = await audit._fetch_user_display_names(mock_db_session, [])
        assert result == {}
        mock_db_session.exec.assert_not_called()

    @pytest.mark.asyncio
    async def test_valid_provider_codes_with_matches(self):
        """Valid provider codes with matching users returns dict mapping."""
        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = [
            ("provider-1", "User One"),
            ("provider-2", "User Two"),
        ]
        mock_session.exec = AsyncMock(return_value=result_mock)

        result = await audit._fetch_user_display_names(
            mock_session, ["provider-1", "provider-2"]
        )

        assert result == {
            "provider-1": "User One",
            "provider-2": "User Two",
        }

    @pytest.mark.asyncio
    async def test_provider_codes_with_no_matches(self):
        """Provider codes with no matches returns empty dict."""
        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        result = await audit._fetch_user_display_names(mock_session, ["nonexistent"])

        assert result == {}

    @pytest.mark.asyncio
    async def test_mixed_matches(self):
        """Mixed matches - some found, some not - returns only found ones."""
        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = [("provider-1", "User One")]
        mock_session.exec = AsyncMock(return_value=result_mock)

        result = await audit._fetch_user_display_names(
            mock_session, ["provider-1", "provider-2"]
        )

        assert result == {"provider-1": "User One"}

    @pytest.mark.asyncio
    async def test_filters_none_display_names(self):
        """Provider codes with None display_name are filtered out."""
        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = [
            ("provider-1", "User One"),
            ("provider-2", None),
            ("provider-3", "User Three"),
        ]
        mock_session.exec = AsyncMock(return_value=result_mock)

        result = await audit._fetch_user_display_names(
            mock_session, ["provider-1", "provider-2", "provider-3"]
        )

        assert result == {
            "provider-1": "User One",
            "provider-3": "User Three",
        }


class TestBuildMessageSummary:
    """Tests for _build_message_summary helper function."""

    def test_all_fields_present(self):
        """Document with all fields populated returns formatted string."""
        doc = MagicMock()
        doc.change_type = AuditChangeTypeEnum.CREATE
        doc.entity_type = "module"
        doc.entity_id = 123
        doc.change_reason = "Initial creation"

        result = audit._build_message_summary(doc)

        assert result == "CREATE module #123 — Initial creation"

    def test_long_change_reason_truncated(self):
        """Long change_reason (>60 chars) is truncated with ellipsis."""
        doc = MagicMock()
        doc.change_type = AuditChangeTypeEnum.UPDATE
        doc.entity_type = "resource"
        doc.entity_id = 456
        doc.change_reason = "A" * 70  # 70 characters

        result = audit._build_message_summary(doc)

        assert result == f"UPDATE resource #456 — {'A' * 57}..."
        assert len(result.split("—")[1].strip()) == 60

    def test_missing_entity_id(self):
        """Missing entity_id is omitted from summary."""
        doc = MagicMock()
        doc.change_type = AuditChangeTypeEnum.DELETE
        doc.entity_type = "unit"
        doc.entity_id = None
        doc.change_reason = "Cascade delete"

        result = audit._build_message_summary(doc)

        assert result == "DELETE unit — Cascade delete"
        assert "#" not in result

    def test_missing_change_reason(self):
        """Missing change_reason is omitted from summary."""
        doc = MagicMock()
        doc.change_type = AuditChangeTypeEnum.READ
        doc.entity_type = "report"
        doc.entity_id = 789
        doc.change_reason = None

        result = audit._build_message_summary(doc)

        assert result == "READ report #789"
        assert "—" not in result

    def test_change_type_as_enum(self):
        """change_type as enum is handled correctly."""
        doc = MagicMock()
        doc.change_type = AuditChangeTypeEnum.UPDATE
        doc.entity_type = "test"
        doc.entity_id = 1
        doc.change_reason = None

        result = audit._build_message_summary(doc)

        assert result.startswith("UPDATE")

    def test_change_type_as_string(self):
        """change_type as string (no .value attribute) is handled correctly."""
        doc = MagicMock()
        doc.change_type = "CREATE"
        doc.entity_type = "test"
        doc.entity_id = 1
        doc.change_reason = None

        result = audit._build_message_summary(doc)

        assert result.startswith("CREATE")


class TestBuildFilters:
    """Tests for _build_filters helper function."""

    def test_all_none_parameters(self):
        """All None parameters returns empty dict."""
        result = audit._build_filters()
        assert result == {}

    def test_individual_filters(self):
        """Each individual filter set returns correct dict."""
        # user_id
        result = audit._build_filters(user_id=1)
        assert result == {"user_id": 1}

        # handler_id
        result = audit._build_filters(handler_id="handler-123")
        assert result == {"handler_id": "handler-123"}

        # entity_type
        result = audit._build_filters(entity_type="module")
        assert result == {"entity_type": "module"}

        # entity_id
        result = audit._build_filters(entity_id=100)
        assert result == {"entity_id": 100}

        # action
        result = audit._build_filters(action="CREATE")
        assert result == {"action": "CREATE"}

        # date_from
        date = datetime(2024, 1, 1)
        result = audit._build_filters(date_from=date)
        assert result == {"date_from": date}

        # date_to
        result = audit._build_filters(date_to=date)
        assert result == {"date_to": date}

        # search
        result = audit._build_filters(search="test")
        assert result == {"search": "test"}

        # module
        result = audit._build_filters(module="units")
        assert result == {"module": "units"}

    def test_multiple_filters_combined(self):
        """Multiple filters combined returns all in dict."""
        date_from = datetime(2024, 1, 1)
        date_to = datetime(2024, 12, 31)

        result = audit._build_filters(
            user_id=1,
            handler_id="handler-123",
            entity_type="module",
            entity_id=100,
            action="UPDATE",
            date_from=date_from,
            date_to=date_to,
            search="test",
            module="units",
        )

        assert result == {
            "user_id": 1,
            "handler_id": "handler-123",
            "entity_type": "module",
            "entity_id": 100,
            "action": "UPDATE",
            "date_from": date_from,
            "date_to": date_to,
            "search": "test",
            "module": "units",
        }

    def test_entity_id_zero_included(self):
        """entity_id=0 (falsy but valid) is included in filters."""
        result = audit._build_filters(entity_id=0)
        assert result == {"entity_id": 0}
        assert "entity_id" in result

    def test_entity_id_none_explicitly_included(self):
        """entity_id=None explicitly passed is included in filters."""
        result = audit._build_filters(entity_id=None)
        # When None is passed, it's not included because of the
        # `if entity_id is not None` check
        assert result == {}


# ============================================================================
# ENDPOINT TESTS - list_audit_logs
# ============================================================================


class TestListAuditLogs:
    """Tests for list_audit_logs endpoint."""

    @pytest.mark.asyncio
    async def test_permission_denied(self, client, mock_auth_deny, mock_user):
        """User without permission receives 403 Forbidden."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        response = client.get("/api/v1/audit/activity")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_successful_list_no_filters(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """Authenticated user with permission gets successful response."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        # Mock repository
        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            response = client.get("/api/v1/audit/activity")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert "data" in data
            assert "pagination" in data
            assert data["pagination"]["total"] == 1
            assert len(data["data"]) == 1
            assert data["data"][0]["id"] == 1

    @pytest.mark.asyncio
    async def test_empty_results(self, client, mock_auth_allow, mock_user):
        """Empty results returns empty list with pagination."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([], 0)

            response = client.get("/api/v1/audit/activity")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["data"] == []
            assert data["pagination"]["total"] == 0

    @pytest.mark.asyncio
    async def test_document_with_no_id_skipped(
        self, client, mock_auth_allow, mock_user
    ):
        """Document with id=None is skipped from results."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        # Create doc with no ID
        doc_no_id = MagicMock(spec=AuditDocument)
        doc_no_id.id = None
        doc_no_id.handler_id = "handler-123"

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([doc_no_id], 1)

            response = client.get("/api/v1/audit/activity")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["data"] == []  # Skipped

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "filter_param,filter_value",
        [
            ("user_id", "1"),
            ("handler_id", "handler-123"),
            ("entity_type", "module"),
            ("entity_id", "100"),
            ("action", "CREATE"),
            ("search", "test"),
            ("module", "units"),
        ],
    )
    async def test_individual_filters(
        self,
        client,
        mock_auth_allow,
        mock_user,
        mock_audit_doc,
        filter_param,
        filter_value,
    ):
        """Each filter parameter is passed correctly to repository."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            response = client.get(
                f"/api/v1/audit/activity?{filter_param}={filter_value}"
            )

            assert response.status_code == status.HTTP_200_OK
            # Verify filter was passed to repository
            call_args = mock_query.call_args
            assert call_args is not None

    @pytest.mark.asyncio
    async def test_pagination_parameters(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """Pagination parameters are handled correctly."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 50)

            response = client.get("/api/v1/audit/activity?page=2&page_size=10")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["pagination"]["page"] == 2
            assert data["pagination"]["page_size"] == 10
            assert data["pagination"]["total"] == 50

            # Verify repository was called with correct pagination
            mock_query.assert_called_once()
            call_kwargs = mock_query.call_args.kwargs
            assert call_kwargs["page"] == 2
            assert call_kwargs["page_size"] == 10

    @pytest.mark.asyncio
    async def test_sorting_parameters(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """Sorting parameters are passed to repository."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            response = client.get(
                "/api/v1/audit/activity?sort_by=entity_type&sort_desc=false"
            )

            assert response.status_code == status.HTTP_200_OK

            # Verify repository was called with correct sorting
            call_kwargs = mock_query.call_args.kwargs
            assert call_kwargs["sort_by"] == "entity_type"
            assert call_kwargs["sort_desc"] is False

    @pytest.mark.asyncio
    async def test_invalid_sort_by_field(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """Invalid sort_by field defaults to changed_at."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            # Use an invalid field name
            response = client.get(
                "/api/v1/audit/activity?sort_by=invalid_field&sort_desc=false"
            )

            assert response.status_code == status.HTTP_200_OK

            # Verify repository was called with default "changed_at"
            call_kwargs = mock_query.call_args.kwargs
            assert call_kwargs["sort_by"] == "changed_at"
            assert call_kwargs["sort_desc"] is False

    @pytest.mark.asyncio
    async def test_display_names_populated(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """Display names are fetched and populated correctly."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = [("handler-123", "Test Handler")]
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            response = client.get("/api/v1/audit/activity")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["data"][0]["changed_by_display_name"] == "Test Handler"


# ============================================================================
# ENDPOINT TESTS - get_audit_stats
# ============================================================================


class TestGetAuditStats:
    """Tests for get_audit_stats endpoint."""

    @pytest.mark.asyncio
    async def test_permission_denied(self, client, mock_auth_deny, mock_user):
        """User without permission receives 403 Forbidden."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        response = client.get("/api/v1/audit/stats")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_stats_no_filters(self, client, mock_auth_allow, mock_user):
        """Stats endpoint returns totals by change type."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "count_by_change_type", new_callable=AsyncMock
        ) as mock_count:
            mock_count.return_value = {
                "CREATE": 10,
                "READ": 20,
                "UPDATE": 15,
                "DELETE": 5,
            }

            response = client.get("/api/v1/audit/stats")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_entries"] == 50
            assert data["creates"] == 10
            assert data["reads"] == 20
            assert data["updates"] == 15
            assert data["deletes"] == 5

    @pytest.mark.asyncio
    async def test_stats_with_filters(self, client, mock_auth_allow, mock_user):
        """Stats respects filter parameters."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "count_by_change_type", new_callable=AsyncMock
        ) as mock_count:
            mock_count.return_value = {"CREATE": 5}

            response = client.get("/api/v1/audit/stats?user_id=1&entity_type=module")

            assert response.status_code == status.HTTP_200_OK
            # Verify filters were passed
            mock_count.assert_called_once()
            filters_arg = (
                mock_count.call_args[1]["filters"]
                if mock_count.call_args[1]
                else mock_count.call_args[0][0]
            )
            assert "user_id" in filters_arg
            assert "entity_type" in filters_arg

    @pytest.mark.asyncio
    async def test_stats_no_matching_records(self, client, mock_auth_allow, mock_user):
        """No matching records returns zeros."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "count_by_change_type", new_callable=AsyncMock
        ) as mock_count:
            mock_count.return_value = {}

            response = client.get("/api/v1/audit/stats")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_entries"] == 0
            assert data["creates"] == 0
            assert data["reads"] == 0
            assert data["updates"] == 0
            assert data["deletes"] == 0

    @pytest.mark.asyncio
    async def test_stats_missing_change_types(self, client, mock_auth_allow, mock_user):
        """Missing change types default to 0."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "count_by_change_type", new_callable=AsyncMock
        ) as mock_count:
            # Only CREATE and UPDATE
            mock_count.return_value = {"CREATE": 10, "UPDATE": 5}

            response = client.get("/api/v1/audit/stats")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["total_entries"] == 15
            assert data["creates"] == 10
            assert data["reads"] == 0  # Missing, defaults to 0
            assert data["updates"] == 5
            assert data["deletes"] == 0  # Missing, defaults to 0


# ============================================================================
# ENDPOINT TESTS - get_audit_log_detail
# ============================================================================


class TestGetAuditLogDetail:
    """Tests for get_audit_log_detail endpoint."""

    @pytest.mark.asyncio
    async def test_permission_denied(self, client, mock_auth_deny, mock_user):
        """User without permission receives 403 Forbidden."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        response = client.get("/api/v1/audit/activity/1")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_valid_log_id(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """Valid log_id returns full detail with snapshot and diff."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = [("handler-123", "Test Handler")]
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "get_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_audit_doc

            response = client.get("/api/v1/audit/activity/1")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["id"] == 1
            assert data["entity_type"] == "test_entity"
            assert "data_snapshot" in data
            assert data["data_snapshot"] == {"key": "value"}
            assert "data_diff" in data

    @pytest.mark.asyncio
    async def test_nonexistent_log_id(self, client, mock_auth_allow, mock_user):
        """Non-existent log_id returns 404 Not Found."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "get_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = None

            response = client.get("/api/v1/audit/activity/999")

            assert response.status_code == status.HTTP_404_NOT_FOUND
            assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_document_with_no_id(self, client, mock_auth_allow, mock_user):
        """Document with id=None returns 500 Internal Server Error."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        doc_no_id = MagicMock(spec=AuditDocument)
        doc_no_id.id = None
        doc_no_id.entity_type = "test"
        doc_no_id.entity_id = 123
        doc_no_id.version = 1
        doc_no_id.change_type = AuditChangeTypeEnum.CREATE
        doc_no_id.change_reason = "Test"
        doc_no_id.changed_by = 1
        doc_no_id.changed_at = datetime(2024, 1, 15)
        doc_no_id.handler_id = "handler-123"
        doc_no_id.handled_ids = []
        doc_no_id.ip_address = "127.0.0.1"
        doc_no_id.route_path = "/api/test"
        doc_no_id.data_snapshot = {}
        doc_no_id.data_diff = None

        with patch.object(
            AuditDocumentRepository, "get_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = doc_no_id

            response = client.get("/api/v1/audit/activity/1")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @pytest.mark.asyncio
    async def test_display_name_populated(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """Display name is fetched and populated from handler_id."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = [("handler-123", "Test Handler")]
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "get_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_audit_doc

            response = client.get("/api/v1/audit/activity/1")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["changed_by_display_name"] == "Test Handler"

    @pytest.mark.asyncio
    async def test_handled_ids_defaults_to_empty_list(
        self, client, mock_auth_allow, mock_user, mock_audit_doc_with_none_handled_ids
    ):
        """handled_ids defaults to empty list if None."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        mock_session = AsyncMock(spec=AsyncSession)
        result_mock = MagicMock()
        result_mock.all.return_value = []
        mock_session.exec = AsyncMock(return_value=result_mock)

        async def override_get_db():
            yield mock_session

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "get_by_id", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = mock_audit_doc_with_none_handled_ids

            response = client.get("/api/v1/audit/activity/1")

            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["handled_ids"] == []


# ============================================================================
# ENDPOINT TESTS - export_audit_logs
# ============================================================================


class TestExportAuditLogs:
    """Tests for export_audit_logs endpoint."""

    @pytest.mark.asyncio
    async def test_permission_denied(self, client, mock_auth_deny, mock_user):
        """User without permission receives 403 Forbidden."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        response = client.get("/api/v1/audit/export")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_csv_export_format(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """CSV export returns correct format and headers."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            with patch("app.api.v1.audit.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2024, 1, 15, tzinfo=timezone.utc)

                response = client.get("/api/v1/audit/export?format=csv")

                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "text/csv; charset=utf-8"
                assert "attachment" in response.headers["content-disposition"]
                assert (
                    "audit_export_2024-01-15.csv"
                    in response.headers["content-disposition"]
                )

                # Parse CSV content
                content = response.text
                lines = content.strip().split("\n")
                assert len(lines) >= 2  # Header + at least one row
                assert "id,entity_type,entity_id" in lines[0]

    @pytest.mark.asyncio
    async def test_csv_export_row_format(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """CSV rows match column headers."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            response = client.get("/api/v1/audit/export?format=csv")

            assert response.status_code == status.HTTP_200_OK
            content = response.text
            lines = content.strip().split("\n")

            # Check that we have data row
            assert len(lines) == 2
            # Row should have entity_id = 123
            assert "123" in lines[1]

    @pytest.mark.asyncio
    async def test_csv_handled_ids_joined(self, client, mock_auth_allow, mock_user):
        """CSV handled_ids are joined with semicolon."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        doc = MagicMock(spec=AuditDocument)
        doc.id = 1
        doc.entity_type = "test"
        doc.entity_id = 123
        doc.version = 1
        doc.change_type = AuditChangeTypeEnum.CREATE
        doc.change_reason = "Test"
        doc.changed_by = 1
        doc.changed_at = datetime(2024, 1, 15)
        doc.handler_id = "handler-1"
        doc.handled_ids = ["handler-1", "handler-2", "handler-3"]
        doc.ip_address = "127.0.0.1"
        doc.route_path = "/api/test"

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([doc], 1)

            response = client.get("/api/v1/audit/export?format=csv")

            assert response.status_code == status.HTTP_200_OK
            content = response.text
            assert "handler-1;handler-2;handler-3" in content

    @pytest.mark.asyncio
    async def test_csv_empty_fields_handled(self, client, mock_auth_allow, mock_user):
        """CSV handles None/empty fields correctly."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        doc = MagicMock(spec=AuditDocument)
        doc.id = 1
        doc.entity_type = "test"
        doc.entity_id = 123
        doc.version = 1
        doc.change_type = AuditChangeTypeEnum.CREATE
        doc.change_reason = None  # None field
        doc.changed_by = 1
        doc.changed_at = datetime(2024, 1, 15)
        doc.handler_id = "handler-1"
        doc.handled_ids = None  # None field
        doc.ip_address = "127.0.0.1"
        doc.route_path = None  # None field

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([doc], 1)

            response = client.get("/api/v1/audit/export?format=csv")

            assert response.status_code == status.HTTP_200_OK
            # Should not raise errors with None values

    @pytest.mark.asyncio
    async def test_json_export_format(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """JSON export returns correct format."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            with patch("app.api.v1.audit.datetime") as mock_dt:
                mock_dt.now.return_value = datetime(2024, 1, 15, tzinfo=timezone.utc)

                response = client.get("/api/v1/audit/export?format=json")

                assert response.status_code == status.HTTP_200_OK
                assert response.headers["content-type"] == "application/json"
                assert "attachment" in response.headers["content-disposition"]
                assert (
                    "audit_export_2024-01-15.json"
                    in response.headers["content-disposition"]
                )

                # Parse JSON content
                import json

                data = json.loads(response.text)
                assert isinstance(data, list)
                assert len(data) == 1
                assert data[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_json_export_all_fields(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """JSON export includes all fields."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            response = client.get("/api/v1/audit/export?format=json")

            assert response.status_code == status.HTTP_200_OK
            import json

            data = json.loads(response.text)

            entry = data[0]
            assert "id" in entry
            assert "entity_type" in entry
            assert "entity_id" in entry
            assert "change_type" in entry
            assert "data_snapshot" in entry
            assert "data_diff" in entry
            assert "handled_ids" in entry

    @pytest.mark.asyncio
    async def test_json_handled_ids_as_array(self, client, mock_auth_allow, mock_user):
        """JSON handled_ids are exported as array."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        doc = MagicMock(spec=AuditDocument)
        doc.id = 1
        doc.entity_type = "test"
        doc.entity_id = 123
        doc.version = 1
        doc.change_type = AuditChangeTypeEnum.CREATE
        doc.change_reason = "Test"
        doc.changed_by = 1
        doc.changed_at = datetime(2024, 1, 15)
        doc.handler_id = "handler-1"
        doc.handled_ids = ["handler-1", "handler-2"]
        doc.ip_address = "127.0.0.1"
        doc.route_path = "/api/test"
        doc.data_snapshot = {}
        doc.data_diff = None

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([doc], 1)

            response = client.get("/api/v1/audit/export?format=json")

            assert response.status_code == status.HTTP_200_OK
            import json

            data = json.loads(response.text)
            assert data[0]["handled_ids"] == ["handler-1", "handler-2"]

    @pytest.mark.asyncio
    async def test_json_datetime_iso_format(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """JSON datetime fields are ISO formatted."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            response = client.get("/api/v1/audit/export?format=json")

            assert response.status_code == status.HTTP_200_OK
            import json

            data = json.loads(response.text)
            # Should be ISO format
            assert data[0]["changed_at"] == "2024-01-15T10:30:00"

    @pytest.mark.asyncio
    async def test_export_empty_results(self, client, mock_auth_allow, mock_user):
        """Export with no results returns empty CSV/JSON."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([], 0)

            # CSV
            response = client.get("/api/v1/audit/export?format=csv")
            assert response.status_code == status.HTTP_200_OK
            lines = response.text.strip().split("\n")
            assert len(lines) == 1  # Just header

            # JSON
            response = client.get("/api/v1/audit/export?format=json")
            assert response.status_code == status.HTTP_200_OK
            import json

            data = json.loads(response.text)
            assert data == []

    @pytest.mark.asyncio
    async def test_export_respects_filters(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """Export applies same filters as list endpoint."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            response = client.get(
                "/api/v1/audit/export?format=csv&user_id=1&entity_type=module"
            )

            assert response.status_code == status.HTTP_200_OK
            # Verify filters were passed
            call_kwargs = mock_query.call_args.kwargs
            assert "user_id" in call_kwargs["filters"]
            assert "entity_type" in call_kwargs["filters"]

    @pytest.mark.asyncio
    async def test_export_10k_cap(
        self, client, mock_auth_allow, mock_user, mock_audit_doc
    ):
        """Export respects 10,000 record cap."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([mock_audit_doc], 1)

            response = client.get("/api/v1/audit/export?format=csv")

            assert response.status_code == status.HTTP_200_OK
            # Verify page_size was capped at 10000
            call_kwargs = mock_query.call_args.kwargs
            assert call_kwargs["page_size"] == 10000

    @pytest.mark.asyncio
    async def test_csv_change_type_enum_handled(
        self, client, mock_auth_allow, mock_user
    ):
        """CSV export handles change_type enum correctly."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        doc = MagicMock(spec=AuditDocument)
        doc.id = 1
        doc.entity_type = "test"
        doc.entity_id = 123
        doc.version = 1
        doc.change_type = AuditChangeTypeEnum.UPDATE  # Enum
        doc.change_reason = None
        doc.changed_by = 1
        doc.changed_at = datetime(2024, 1, 15)
        doc.handler_id = "handler-1"
        doc.handled_ids = []
        doc.ip_address = "127.0.0.1"
        doc.route_path = "/api/test"

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([doc], 1)

            response = client.get("/api/v1/audit/export?format=csv")

            assert response.status_code == status.HTTP_200_OK
            content = response.text
            assert "UPDATE" in content

    @pytest.mark.asyncio
    async def test_json_change_type_converted_to_string(
        self, client, mock_auth_allow, mock_user
    ):
        """JSON export converts change_type enum to string."""
        from app.api.deps import get_db
        from app.core.security import get_current_active_user
        from app.repositories.audit_repo import AuditDocumentRepository

        async def override_get_db():
            yield AsyncMock(spec=AsyncSession)

        app.dependency_overrides[get_db] = override_get_db
        app.dependency_overrides[get_current_active_user] = lambda: mock_user

        doc = MagicMock(spec=AuditDocument)
        doc.id = 1
        doc.entity_type = "test"
        doc.entity_id = 123
        doc.version = 1
        doc.change_type = AuditChangeTypeEnum.DELETE  # Enum
        doc.change_reason = None
        doc.changed_by = 1
        doc.changed_at = datetime(2024, 1, 15)
        doc.handler_id = "handler-1"
        doc.handled_ids = []
        doc.ip_address = "127.0.0.1"
        doc.route_path = "/api/test"
        doc.data_snapshot = {}
        doc.data_diff = None

        with patch.object(
            AuditDocumentRepository, "query", new_callable=AsyncMock
        ) as mock_query:
            mock_query.return_value = ([doc], 1)

            response = client.get("/api/v1/audit/export?format=json")

            assert response.status_code == status.HTTP_200_OK
            import json

            data = json.loads(response.text)
            assert data[0]["change_type"] == "DELETE"
            assert isinstance(data[0]["change_type"], str)
