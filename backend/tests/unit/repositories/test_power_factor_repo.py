"""Unit tests for PowerFactorRepository."""

from datetime import datetime

import pytest
import pytest_asyncio
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.emission_factor import PowerFactor
from app.repositories.power_factor_repo import PowerFactorRepository


@pytest_asyncio.fixture
async def power_factor_repo():
    """Create a PowerFactorRepository instance."""
    return PowerFactorRepository()


@pytest_asyncio.fixture
async def sample_power_factors(db_session: AsyncSession):
    """Create sample power factors for testing."""
    factors = [
        # Scientific equipment - Centrifugation with subclasses
        PowerFactor(
            submodule="scientific",
            equipment_class="Centrifugation",
            sub_class="Ultra centrifuges",
            active_power_w=1300.0,
            standby_power_w=130.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test data",
            power_metadata={},
        ),
        PowerFactor(
            submodule="scientific",
            equipment_class="Centrifugation",
            sub_class="Microcentrifuges",
            active_power_w=300.0,
            standby_power_w=30.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test data",
            power_metadata={},
        ),
        # Scientific equipment - Centrifugation class-level fallback
        PowerFactor(
            submodule="scientific",
            equipment_class="Centrifugation",
            sub_class=None,
            active_power_w=800.0,
            standby_power_w=80.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test data - generic",
            power_metadata={},
        ),
        # Scientific equipment - Microscopy without subclasses
        PowerFactor(
            submodule="scientific",
            equipment_class="Microscopy",
            sub_class=None,
            active_power_w=500.0,
            standby_power_w=50.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test data",
            power_metadata={},
        ),
        # IT equipment - Desktop computers
        PowerFactor(
            submodule="it",
            equipment_class="Desktop Computers",
            sub_class="Workstation",
            active_power_w=200.0,
            standby_power_w=20.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test data",
            power_metadata={},
        ),
        PowerFactor(
            submodule="it",
            equipment_class="Desktop Computers",
            sub_class=None,
            active_power_w=150.0,
            standby_power_w=15.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test data - generic",
            power_metadata={},
        ),
        # Multiple versions - newer one should be preferred
        PowerFactor(
            submodule="it",
            equipment_class="Laptops",
            sub_class=None,
            active_power_w=50.0,
            standby_power_w=5.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=datetime(2024, 12, 31),
            source="Test data - old",
            power_metadata={},
        ),
        PowerFactor(
            submodule="it",
            equipment_class="Laptops",
            sub_class=None,
            active_power_w=45.0,
            standby_power_w=4.5,
            version=2,
            valid_from=datetime(2025, 1, 1),
            valid_to=None,
            source="Test data - new",
            power_metadata={},
        ),
    ]

    for factor in factors:
        db_session.add(factor)
    await db_session.commit()

    return factors


class TestListClasses:
    """Tests for list_classes method."""

    @pytest.mark.asyncio
    async def test_list_classes_scientific(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test listing classes for scientific submodule."""
        classes = await power_factor_repo.list_classes(db_session, "scientific")

        assert len(classes) == 2
        assert "Centrifugation" in classes
        assert "Microscopy" in classes
        # Should be ordered alphabetically
        assert classes == sorted(classes)

    @pytest.mark.asyncio
    async def test_list_classes_it(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test listing classes for IT submodule."""
        classes = await power_factor_repo.list_classes(db_session, "it")

        assert len(classes) == 2
        assert "Desktop Computers" in classes
        assert "Laptops" in classes
        assert classes == sorted(classes)

    @pytest.mark.asyncio
    async def test_list_classes_empty_submodule(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test listing classes for non-existent submodule returns empty list."""
        classes = await power_factor_repo.list_classes(db_session, "nonexistent")

        assert classes == []

    @pytest.mark.asyncio
    async def test_list_classes_distinct(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test that classes are returned as distinct values."""
        # Centrifugation appears 3 times in sample data, should only appear once
        classes = await power_factor_repo.list_classes(db_session, "scientific")

        assert classes.count("Centrifugation") == 1


class TestGetPowerFactor:
    """Tests for get_power_factor method."""

    @pytest.mark.asyncio
    async def test_get_power_factor_exact_match(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test getting power factor with exact subclass match."""
        factor = await power_factor_repo.get_power_factor(
            db_session,
            submodule="scientific",
            equipment_class="Centrifugation",
            sub_class="Ultra centrifuges",
        )

        assert factor is not None
        assert factor.submodule == "scientific"
        assert factor.equipment_class == "Centrifugation"
        assert factor.sub_class == "Ultra centrifuges"
        assert factor.active_power_w == 1300.0
        assert factor.standby_power_w == 130.0

    @pytest.mark.asyncio
    async def test_get_power_factor_fallback_to_class(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test fallback to class-level when subclass not found."""
        factor = await power_factor_repo.get_power_factor(
            db_session,
            submodule="scientific",
            equipment_class="Centrifugation",
            sub_class="NonexistentSubclass",
        )

        assert factor is not None
        assert factor.submodule == "scientific"
        assert factor.equipment_class == "Centrifugation"
        assert factor.sub_class is None  # Class-level fallback
        assert factor.active_power_w == 800.0
        assert factor.standby_power_w == 80.0

    @pytest.mark.asyncio
    async def test_get_power_factor_no_subclass_provided(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test getting power factor without providing subclass."""
        factor = await power_factor_repo.get_power_factor(
            db_session,
            submodule="scientific",
            equipment_class="Microscopy",
            sub_class=None,
        )

        assert factor is not None
        assert factor.submodule == "scientific"
        assert factor.equipment_class == "Microscopy"
        assert factor.sub_class is None
        assert factor.active_power_w == 500.0

    @pytest.mark.asyncio
    async def test_get_power_factor_prefers_recent_version(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test that most recent version is returned."""
        factor = await power_factor_repo.get_power_factor(
            db_session,
            submodule="it",
            equipment_class="Laptops",
            sub_class=None,
        )

        assert factor is not None
        assert factor.version == 2  # Newer version
        assert factor.active_power_w == 45.0
        assert factor.valid_from == datetime(2025, 1, 1)

    @pytest.mark.asyncio
    async def test_get_power_factor_not_found(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test getting power factor when no match exists."""
        factor = await power_factor_repo.get_power_factor(
            db_session,
            submodule="nonexistent",
            equipment_class="Nonexistent",
            sub_class=None,
        )

        assert factor is None

    @pytest.mark.asyncio
    async def test_get_power_factor_subclass_no_class_fallback(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test that subclass search falls back to class when no match."""
        # Microscopy has only class-level, no subclass entries
        factor = await power_factor_repo.get_power_factor(
            db_session,
            submodule="scientific",
            equipment_class="Microscopy",
            sub_class="SomeSubclass",
        )

        assert factor is not None
        assert factor.sub_class is None  # Fallback to class-level
        assert factor.equipment_class == "Microscopy"


class TestListSubclasses:
    """Tests for list_subclasses method."""

    @pytest.mark.asyncio
    async def test_list_subclasses_centrifugation(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test listing subclasses for Centrifugation."""
        subclasses = await power_factor_repo.list_subclasses(
            db_session, "scientific", "Centrifugation"
        )

        assert len(subclasses) == 2
        assert "Ultra centrifuges" in subclasses
        assert "Microcentrifuges" in subclasses
        # Should be ordered alphabetically
        assert subclasses == sorted(subclasses)

    @pytest.mark.asyncio
    async def test_list_subclasses_no_subclasses(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test listing subclasses for class with only class-level entry."""
        subclasses = await power_factor_repo.list_subclasses(
            db_session, "scientific", "Microscopy"
        )

        assert subclasses == []

    @pytest.mark.asyncio
    async def test_list_subclasses_nonexistent_class(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test listing subclasses for non-existent class."""
        subclasses = await power_factor_repo.list_subclasses(
            db_session, "scientific", "Nonexistent"
        )

        assert subclasses == []

    @pytest.mark.asyncio
    async def test_list_subclasses_filters_none(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test that None subclasses are filtered out."""
        # Centrifugation has one None subclass entry (class-level)
        subclasses = await power_factor_repo.list_subclasses(
            db_session, "scientific", "Centrifugation"
        )

        # Should only return actual subclasses, not None
        assert None not in subclasses
        assert len(subclasses) == 2

    @pytest.mark.asyncio
    async def test_list_subclasses_distinct(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
    ):
        """Test that subclasses are returned as distinct values."""
        # Add duplicate subclass entries
        factors = [
            PowerFactor(
                submodule="test",
                equipment_class="TestClass",
                sub_class="Duplicate",
                active_power_w=100.0,
                standby_power_w=10.0,
                version=1,
                valid_from=datetime(2024, 1, 1),
                valid_to=None,
                source="Test",
                power_metadata={},
            ),
            PowerFactor(
                submodule="test",
                equipment_class="TestClass",
                sub_class="Duplicate",
                active_power_w=200.0,
                standby_power_w=20.0,
                version=2,
                valid_from=datetime(2024, 6, 1),
                valid_to=None,
                source="Test",
                power_metadata={},
            ),
        ]
        for factor in factors:
            db_session.add(factor)
        await db_session.commit()

        subclasses = await power_factor_repo.list_subclasses(
            db_session, "test", "TestClass"
        )

        assert subclasses.count("Duplicate") == 1


class TestGetClassSubclassMap:
    """Tests for get_class_subclass_map method."""

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_scientific(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test getting class-subclass map for scientific submodule."""
        mapping = await power_factor_repo.get_class_subclass_map(
            db_session, "scientific"
        )

        assert len(mapping) == 2
        assert "Centrifugation" in mapping
        assert "Microscopy" in mapping

        # Centrifugation has 2 subclasses
        assert len(mapping["Centrifugation"]) == 2
        assert "Ultra centrifuges" in mapping["Centrifugation"]
        assert "Microcentrifuges" in mapping["Centrifugation"]
        # Should be sorted
        assert mapping["Centrifugation"] == sorted(mapping["Centrifugation"])

        # Microscopy has no subclasses
        assert mapping["Microscopy"] == []

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_it(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test getting class-subclass map for IT submodule."""
        mapping = await power_factor_repo.get_class_subclass_map(db_session, "it")

        assert len(mapping) == 2
        assert "Desktop Computers" in mapping
        assert "Laptops" in mapping

        # Desktop Computers has 1 subclass
        assert mapping["Desktop Computers"] == ["Workstation"]

        # Laptops has no subclasses
        assert mapping["Laptops"] == []

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_empty_submodule(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
        sample_power_factors,
    ):
        """Test getting map for non-existent submodule."""
        mapping = await power_factor_repo.get_class_subclass_map(
            db_session, "nonexistent"
        )

        assert mapping == {}

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_includes_all_classes(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
    ):
        """Test that map includes all classes even without subclasses."""
        # Add a class with only class-level entry
        factor = PowerFactor(
            submodule="other",
            equipment_class="OnlyClassLevel",
            sub_class=None,
            active_power_w=100.0,
            standby_power_w=10.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test",
            power_metadata={},
        )
        db_session.add(factor)
        await db_session.commit()

        mapping = await power_factor_repo.get_class_subclass_map(db_session, "other")

        assert "OnlyClassLevel" in mapping
        assert mapping["OnlyClassLevel"] == []

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_no_duplicates(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
    ):
        """Test that subclasses appear only once in the map."""
        # Add duplicate subclass entries
        factors = [
            PowerFactor(
                submodule="test",
                equipment_class="TestClass",
                sub_class="SubA",
                active_power_w=100.0,
                standby_power_w=10.0,
                version=1,
                valid_from=datetime(2024, 1, 1),
                valid_to=None,
                source="Test",
                power_metadata={},
            ),
            PowerFactor(
                submodule="test",
                equipment_class="TestClass",
                sub_class="SubA",
                active_power_w=200.0,
                standby_power_w=20.0,
                version=2,
                valid_from=datetime(2024, 6, 1),
                valid_to=None,
                source="Test",
                power_metadata={},
            ),
            PowerFactor(
                submodule="test",
                equipment_class="TestClass",
                sub_class="SubB",
                active_power_w=150.0,
                standby_power_w=15.0,
                version=1,
                valid_from=datetime(2024, 1, 1),
                valid_to=None,
                source="Test",
                power_metadata={},
            ),
        ]
        for factor in factors:
            db_session.add(factor)
        await db_session.commit()

        mapping = await power_factor_repo.get_class_subclass_map(db_session, "test")

        assert mapping["TestClass"].count("SubA") == 1
        assert len(mapping["TestClass"]) == 2
        assert mapping["TestClass"] == sorted(mapping["TestClass"])

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_filters_none_values(
        self,
        db_session: AsyncSession,
        power_factor_repo: PowerFactorRepository,
    ):
        """Test that None values are properly filtered."""
        # Add entries with None values
        factors = [
            PowerFactor(
                submodule="test",
                equipment_class="TestClass",
                sub_class=None,
                active_power_w=100.0,
                standby_power_w=10.0,
                version=1,
                valid_from=datetime(2024, 1, 1),
                valid_to=None,
                source="Test",
                power_metadata={},
            ),
            PowerFactor(
                submodule="test",
                equipment_class="TestClass",
                sub_class="ActualSubclass",
                active_power_w=200.0,
                standby_power_w=20.0,
                version=1,
                valid_from=datetime(2024, 1, 1),
                valid_to=None,
                source="Test",
                power_metadata={},
            ),
        ]
        for factor in factors:
            db_session.add(factor)
        await db_session.commit()

        mapping = await power_factor_repo.get_class_subclass_map(db_session, "test")

        assert None not in mapping["TestClass"]
        assert "ActualSubclass" in mapping["TestClass"]
        assert len(mapping["TestClass"]) == 1
