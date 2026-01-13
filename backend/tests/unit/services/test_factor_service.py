"""Unit tests for FactorService."""

from datetime import datetime, timezone
from typing import Dict, List
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
import pytest_asyncio

from app.models.factor import Factor
from app.repositories.factor_repo import FactorRepository
from app.services.document_versioning_service import DocumentVersioningService
from app.services.factor_service import FactorService


@pytest_asyncio.fixture
async def mock_repo():
    """Create a mock FactorRepository."""
    repo = Mock(spec=FactorRepository)
    repo.get_by_id = AsyncMock()
    repo.get_current_factor = AsyncMock()
    repo.get_power_factor = AsyncMock()
    repo.list_by_family = AsyncMock()
    repo.list_power_classes = AsyncMock()
    repo.list_power_subclasses = AsyncMock()
    repo.get_class_subclass_map = AsyncMock()
    repo.create = AsyncMock()
    repo.expire_factor = AsyncMock()
    repo.find_modules_for_recalculation = AsyncMock()
    return repo


@pytest_asyncio.fixture
async def mock_versioning():
    """Create a mock DocumentVersioningService."""
    versioning = Mock(spec=DocumentVersioningService)
    versioning.create_version = AsyncMock()
    versioning.list_versions = AsyncMock()
    versioning.get_version = AsyncMock()
    return versioning


@pytest_asyncio.fixture
async def mock_session():
    """Create a mock database session."""
    session = MagicMock()
    session.add = Mock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def sample_factor():
    """Create a sample factor for testing."""
    return Factor(
        id=1,
        factor_family="power",
        variant_type_id=9,
        classification={"class": "Centrifugation", "sub_class": "Ultra centrifuges"},
        values={"active_power_w": 1300, "standby_power_w": 130},
        unit={"active_power_w": "W", "standby_power_w": "W"},
        version=1,
        valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        valid_to=None,
        source="Test source",
        meta={},
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_by="test_user",
    )


class TestFactorServiceInit:
    """Tests for FactorService initialization."""

    def test_init_with_default_dependencies(self):
        """Test service initialization with default dependencies."""
        service = FactorService()

        assert service.repo is not None
        assert service.versioning is not None

    def test_init_with_custom_dependencies(self, mock_repo, mock_versioning):
        """Test service initialization with custom dependencies."""
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        assert service.repo is mock_repo
        assert service.versioning is mock_versioning


class TestGetById:
    """Tests for get_by_id method."""

    @pytest.mark.asyncio
    async def test_get_by_id_returns_factor(
        self, mock_repo, mock_versioning, mock_session, sample_factor
    ):
        """Test get_by_id returns factor when found."""
        mock_repo.get_by_id.return_value = sample_factor
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.get_by_id(mock_session, 1)

        mock_repo.get_by_id.assert_called_once_with(mock_session, 1)
        assert result == sample_factor

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none(
        self, mock_repo, mock_versioning, mock_session
    ):
        """Test get_by_id returns None when not found."""
        mock_repo.get_by_id.return_value = None
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.get_by_id(mock_session, 999)

        assert result is None


class TestGetPowerFactor:
    """Tests for get_power_factor method."""

    @pytest.mark.asyncio
    async def test_get_power_factor_returns_factor(
        self, mock_repo, mock_versioning, mock_session, sample_factor
    ):
        """Test get_power_factor returns factor when found."""
        mock_repo.get_power_factor.return_value = sample_factor
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.get_power_factor(
            mock_session, 9, "Centrifugation", "Ultra centrifuges"
        )

        mock_repo.get_power_factor.assert_called_once_with(
            mock_session, 9, "Centrifugation", "Ultra centrifuges"
        )
        assert result == sample_factor


class TestGetHeadcountFactor:
    """Tests for get_headcount_factor method."""

    @pytest.mark.asyncio
    async def test_get_headcount_factor_returns_factor(
        self, mock_repo, mock_versioning, mock_session
    ):
        """Test get_headcount_factor returns factor when found."""
        headcount_factor = Factor(
            id=2,
            factor_family="headcount",
            variant_type_id=1,
            classification={},
            values={
                "food_kg": 420,
                "waste_kg": 65,
                "transport_kg": 350,
                "grey_energy_kg": 120,
            },
            version=1,
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        mock_repo.get_current_factor.return_value = headcount_factor
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.get_headcount_factor(mock_session, 1)

        mock_repo.get_current_factor.assert_called_once_with(
            mock_session, factor_family="headcount", variant_type_id=1
        )
        assert result == headcount_factor


class TestCreateFactor:
    """Tests for create_factor method."""

    @pytest.mark.asyncio
    async def test_create_factor_creates_and_versions(
        self, mock_repo, mock_versioning, mock_session
    ):
        """Test create_factor creates factor and document version."""
        created_factor = Factor(
            id=1,
            factor_family="power",
            variant_type_id=9,
            classification={"class": "Test"},
            values={"power_w": 100},
            version=1,
            valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            created_by="test_user",
        )
        mock_repo.create.return_value = created_factor
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.create_factor(
            session=mock_session,
            factor_family="power",
            values={"power_w": 100},
            created_by="test_user",
            variant_type_id=9,
            classification={"class": "Test"},
            change_reason="Initial creation",
        )

        # Verify factor was created
        mock_repo.create.assert_called_once()
        created_arg = mock_repo.create.call_args[0][1]
        assert created_arg.factor_family == "power"
        assert created_arg.values == {"power_w": 100}

        # Verify document version was created
        mock_versioning.create_version.assert_called_once()
        version_call = mock_versioning.create_version.call_args
        assert version_call.kwargs["entity_type"] == "factors"
        assert version_call.kwargs["change_type"] == "CREATE"
        assert version_call.kwargs["changed_by"] == "test_user"


class TestUpdateFactor:
    """Tests for update_factor method."""

    @pytest.mark.asyncio
    async def test_update_factor_creates_new_version(
        self, mock_repo, mock_versioning, mock_session, sample_factor
    ):
        """Test update_factor expires old and creates new factor."""
        mock_repo.get_by_id.return_value = sample_factor

        updated_factor = Factor(
            id=2,
            factor_family="power",
            variant_type_id=9,
            classification={
                "class": "Centrifugation",
                "sub_class": "Ultra centrifuges",
            },
            values={"active_power_w": 1400, "standby_power_w": 140},
            version=2,
            valid_from=datetime(2026, 1, 8, tzinfo=timezone.utc),
            created_at=datetime(2026, 1, 8, tzinfo=timezone.utc),
            created_by="updater",
        )
        mock_repo.create.return_value = updated_factor
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.update_factor(
            session=mock_session,
            factor_id=1,
            updated_by="updater",
            values={"active_power_w": 1400, "standby_power_w": 140},
            change_reason="Updated power values",
        )

        # Verify old factor was fetched
        mock_repo.get_by_id.assert_called_once_with(mock_session, 1)

        # Verify new factor was created with incremented version
        mock_repo.create.assert_called_once()
        created_arg = mock_repo.create.call_args[0][1]
        assert created_arg.version == 2
        assert created_arg.values == {"active_power_w": 1400, "standby_power_w": 140}

        # Verify document version was created
        mock_versioning.create_version.assert_called_once()
        version_call = mock_versioning.create_version.call_args
        assert version_call.kwargs["change_type"] == "UPDATE"

    @pytest.mark.asyncio
    async def test_update_factor_returns_none_when_not_found(
        self, mock_repo, mock_versioning, mock_session
    ):
        """Test update_factor returns None when factor not found."""
        mock_repo.get_by_id.return_value = None
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.update_factor(
            session=mock_session,
            factor_id=999,
            updated_by="updater",
            values={"power_w": 200},
        )

        assert result is None
        mock_repo.create.assert_not_called()
        mock_versioning.create_version.assert_not_called()


class TestExpireFactor:
    """Tests for expire_factor method."""

    @pytest.mark.asyncio
    async def test_expire_factor_creates_delete_version(
        self, mock_repo, mock_versioning, mock_session, sample_factor
    ):
        """Test expire_factor marks factor as expired and creates version."""
        sample_factor.valid_to = datetime(2026, 1, 8, tzinfo=timezone.utc)
        mock_repo.expire_factor.return_value = sample_factor
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.expire_factor(
            session=mock_session,
            factor_id=1,
            expired_by="admin",
            change_reason="No longer needed",
        )

        mock_repo.expire_factor.assert_called_once_with(mock_session, 1)
        mock_versioning.create_version.assert_called_once()
        version_call = mock_versioning.create_version.call_args
        assert version_call.kwargs["change_type"] == "DELETE"


class TestListByFamily:
    """Tests for list_by_family method."""

    @pytest.mark.asyncio
    async def test_list_by_family_returns_factors(
        self, mock_repo, mock_versioning, mock_session, sample_factor
    ):
        """Test list_by_family returns list of factors."""
        mock_repo.list_by_family.return_value = [sample_factor]
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.list_by_family(mock_session, "power")

        mock_repo.list_by_family.assert_called_once_with(mock_session, "power", False)
        assert result == [sample_factor]


class TestGetVersionHistory:
    """Tests for get_version_history method."""

    @pytest.mark.asyncio
    async def test_get_version_history_returns_formatted_list(
        self, mock_repo, mock_versioning, mock_session
    ):
        """Test get_version_history returns formatted version list."""
        mock_version = Mock()
        mock_version.version = 1
        mock_version.change_type = "CREATE"
        mock_version.change_reason = "Initial"
        mock_version.changed_by = "admin"
        mock_version.changed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        mock_version.data_diff = None

        mock_versioning.list_versions.return_value = [mock_version]
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.get_version_history(mock_session, 1)

        mock_versioning.list_versions.assert_called_once_with(
            mock_session, "factors", 1
        )
        assert len(result) == 1
        assert result[0]["version"] == 1
        assert result[0]["change_type"] == "CREATE"


class TestFindModulesForRecalculation:
    """Tests for find_modules_for_recalculation method."""

    @pytest.mark.asyncio
    async def test_find_modules_returns_list(
        self, mock_repo, mock_versioning, mock_session
    ):
        """Test find_modules_for_recalculation returns module IDs."""
        mock_repo.find_modules_for_recalculation.return_value = [1, 2, 3]
        service = FactorService(repo=mock_repo, versioning_service=mock_versioning)

        result = await service.find_modules_for_recalculation(mock_session, 1)

        mock_repo.find_modules_for_recalculation.assert_called_once_with(
            mock_session, 1
        )
        assert result == [1, 2, 3]
