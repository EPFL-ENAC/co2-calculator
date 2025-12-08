"""Unit tests for PowerFactorService."""

from typing import Dict, List
from unittest.mock import AsyncMock, Mock

import pytest
import pytest_asyncio

from app.models.emission_factor import PowerFactor
from app.repositories.power_factor_repo import PowerFactorRepository
from app.services.power_factor_service import PowerFactorService


@pytest_asyncio.fixture
async def mock_repo():
    """Create a mock PowerFactorRepository."""
    repo = Mock(spec=PowerFactorRepository)
    # Make all methods async mocks
    repo.list_classes = AsyncMock()
    repo.list_subclasses = AsyncMock()
    repo.get_power_factor = AsyncMock()
    repo.get_class_subclass_map = AsyncMock()
    return repo


@pytest_asyncio.fixture
async def mock_session():
    """Create a mock database session."""
    return Mock()


class TestPowerFactorServiceInit:
    """Tests for PowerFactorService initialization."""

    def test_init_with_default_repo(self):
        """Test service initialization with default repository."""
        service = PowerFactorService()

        assert service.repo is not None
        assert isinstance(service.repo, PowerFactorRepository)

    def test_init_with_custom_repo(self, mock_repo):
        """Test service initialization with custom repository."""
        service = PowerFactorService(repo=mock_repo)

        assert service.repo is mock_repo

    def test_init_with_none_creates_default(self):
        """Test that passing None creates default repository."""
        service = PowerFactorService(repo=None)

        assert service.repo is not None
        assert isinstance(service.repo, PowerFactorRepository)


class TestGetClasses:
    """Tests for get_classes method."""

    @pytest.mark.asyncio
    async def test_get_classes_delegates_to_repo(self, mock_repo, mock_session):
        """Test that get_classes properly delegates to repository."""
        mock_repo.list_classes.return_value = ["Class1", "Class2"]
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_classes(mock_session, "scientific")

        mock_repo.list_classes.assert_called_once_with(mock_session, "scientific")
        assert result == ["Class1", "Class2"]

    @pytest.mark.asyncio
    async def test_get_classes_returns_empty_list(self, mock_repo, mock_session):
        """Test get_classes when repository returns empty list."""
        mock_repo.list_classes.return_value = []
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_classes(mock_session, "nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_classes_with_different_submodules(self, mock_repo, mock_session):
        """Test get_classes with different submodule parameters."""
        mock_repo.list_classes.return_value = ["IT Class"]
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_classes(mock_session, "it")

        mock_repo.list_classes.assert_called_once_with(mock_session, "it")
        assert result == ["IT Class"]


class TestGetSubclasses:
    """Tests for get_subclasses method."""

    @pytest.mark.asyncio
    async def test_get_subclasses_delegates_to_repo(self, mock_repo, mock_session):
        """Test that get_subclasses properly delegates to repository."""
        mock_repo.list_subclasses.return_value = ["Subclass1", "Subclass2"]
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_subclasses(
            mock_session, "scientific", "Centrifugation"
        )

        mock_repo.list_subclasses.assert_called_once_with(
            mock_session, "scientific", "Centrifugation"
        )
        assert result == ["Subclass1", "Subclass2"]

    @pytest.mark.asyncio
    async def test_get_subclasses_returns_empty_list(self, mock_repo, mock_session):
        """Test get_subclasses when repository returns empty list."""
        mock_repo.list_subclasses.return_value = []
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_subclasses(mock_session, "scientific", "Microscopy")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_subclasses_passes_parameters_correctly(
        self, mock_repo, mock_session
    ):
        """Test that parameters are passed correctly to repository."""
        mock_repo.list_subclasses.return_value = []
        service = PowerFactorService(repo=mock_repo)

        await service.get_subclasses(mock_session, "it", "Desktop Computers")

        mock_repo.list_subclasses.assert_called_once_with(
            mock_session, "it", "Desktop Computers"
        )


class TestGetPowerFactor:
    """Tests for get_power_factor method."""

    @pytest.mark.asyncio
    async def test_get_power_factor_delegates_to_repo(self, mock_repo, mock_session):
        """Test that get_power_factor properly delegates to repository."""
        mock_power_factor = Mock(spec=PowerFactor)
        mock_power_factor.submodule = "scientific"
        mock_power_factor.equipment_class = "Centrifugation"
        mock_power_factor.sub_class = "Ultra centrifuges"
        mock_power_factor.active_power_w = 1300.0
        mock_power_factor.standby_power_w = 130.0

        mock_repo.get_power_factor.return_value = mock_power_factor
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_power_factor(
            mock_session, "scientific", "Centrifugation", "Ultra centrifuges"
        )

        mock_repo.get_power_factor.assert_called_once_with(
            mock_session, "scientific", "Centrifugation", "Ultra centrifuges"
        )
        assert result == mock_power_factor

    @pytest.mark.asyncio
    async def test_get_power_factor_returns_none(self, mock_repo, mock_session):
        """Test get_power_factor when repository returns None."""
        mock_repo.get_power_factor.return_value = None
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_power_factor(
            mock_session, "nonexistent", "Nonexistent", None
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_power_factor_with_subclass(self, mock_repo, mock_session):
        """Test get_power_factor with subclass parameter."""
        mock_power_factor = Mock(spec=PowerFactor)
        mock_repo.get_power_factor.return_value = mock_power_factor
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_power_factor(
            mock_session, "scientific", "Centrifugation", "Microcentrifuges"
        )

        mock_repo.get_power_factor.assert_called_once_with(
            mock_session, "scientific", "Centrifugation", "Microcentrifuges"
        )
        assert result == mock_power_factor

    @pytest.mark.asyncio
    async def test_get_power_factor_without_subclass(self, mock_repo, mock_session):
        """Test get_power_factor without subclass parameter."""
        mock_power_factor = Mock(spec=PowerFactor)
        mock_repo.get_power_factor.return_value = mock_power_factor
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_power_factor(
            mock_session, "scientific", "Microscopy", None
        )

        mock_repo.get_power_factor.assert_called_once_with(
            mock_session, "scientific", "Microscopy", None
        )
        assert result == mock_power_factor


class TestGetClassSubclassMap:
    """Tests for get_class_subclass_map method."""

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_delegates_to_repo(
        self, mock_repo, mock_session
    ):
        """Test that get_class_subclass_map properly delegates to repository."""
        mock_mapping: Dict[str, List[str]] = {
            "Centrifugation": ["Ultra centrifuges", "Microcentrifuges"],
            "Microscopy": [],
        }
        mock_repo.get_class_subclass_map.return_value = mock_mapping
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_class_subclass_map(mock_session, "scientific")

        mock_repo.get_class_subclass_map.assert_called_once_with(
            mock_session, "scientific"
        )
        assert result == mock_mapping

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_returns_empty_dict(
        self, mock_repo, mock_session
    ):
        """Test get_class_subclass_map when repository returns empty dict."""
        mock_repo.get_class_subclass_map.return_value = {}
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_class_subclass_map(mock_session, "nonexistent")

        assert result == {}

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_passes_submodule_correctly(
        self, mock_repo, mock_session
    ):
        """Test that submodule parameter is passed correctly."""
        mock_mapping: Dict[str, List[str]] = {
            "Desktop Computers": ["Workstation"],
        }
        mock_repo.get_class_subclass_map.return_value = mock_mapping
        service = PowerFactorService(repo=mock_repo)

        result = await service.get_class_subclass_map(mock_session, "it")

        mock_repo.get_class_subclass_map.assert_called_once_with(mock_session, "it")
        assert result == mock_mapping
