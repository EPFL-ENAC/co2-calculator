"""Integration tests for power_factors API endpoints."""

from datetime import datetime

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.emission_factor import PowerFactor


@pytest_asyncio.fixture
async def sample_power_factors(db_session: AsyncSession):
    """Create sample power factors for API testing."""
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
        # Scientific equipment - Microscopy
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
        # Equipment class with slash in name
        PowerFactor(
            submodule="scientific",
            equipment_class="Cell culture / Incubation",
            sub_class="CO2 incubators",
            active_power_w=250.0,
            standby_power_w=25.0,
            version=1,
            valid_from=datetime(2024, 1, 1),
            valid_to=None,
            source="Test data",
            power_metadata={},
        ),
        # IT equipment
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
    ]

    for factor in factors:
        db_session.add(factor)
    await db_session.commit()

    return factors


class TestListClasses:
    """Tests for GET /{submodule}/classes endpoint."""

    @pytest.mark.asyncio
    async def test_list_classes_success(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test successfully listing equipment classes."""
        response = await client.get("/api/v1/power-factors/scientific/classes")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        assert len(data["items"]) == 3
        assert "Centrifugation" in data["items"]
        assert "Microscopy" in data["items"]
        assert "Cell culture / Incubation" in data["items"]
        # Should be alphabetically sorted
        assert data["items"] == sorted(data["items"])

    @pytest.mark.asyncio
    async def test_list_classes_different_submodule(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test listing classes for different submodule."""
        response = await client.get("/api/v1/power-factors/it/classes")

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert "Desktop Computers" in data["items"]

    @pytest.mark.asyncio
    async def test_list_classes_empty_submodule(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test listing classes for submodule with no data."""
        response = await client.get("/api/v1/power-factors/nonexistent/classes")

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_classes_response_model(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test response conforms to EquipmentClassList schema."""
        response = await client.get("/api/v1/power-factors/scientific/classes")

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        for item in data["items"]:
            assert isinstance(item, str)


class TestListSubclasses:
    """Tests for GET /{submodule}/classes/{equipment_class}/subclasses."""

    @pytest.mark.asyncio
    async def test_list_subclasses_success(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test successfully listing subclasses."""
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/Centrifugation/subclasses"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) == 2
        assert "Ultra centrifuges" in data["items"]
        assert "Microcentrifuges" in data["items"]
        assert data["items"] == sorted(data["items"])

    @pytest.mark.asyncio
    async def test_list_subclasses_no_subclasses(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test listing subclasses for class with only class-level entry."""
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/Microscopy/subclasses"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_subclasses_path_normalization(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test path parameter normalization for slashes."""
        # URL-encoded slash in equipment_class name
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/"
            "Cell culture/Incubation/subclasses"
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert "CO2 incubators" in data["items"]

    @pytest.mark.asyncio
    async def test_list_subclasses_nonexistent_class(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test listing subclasses for non-existent class."""
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/Nonexistent/subclasses"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []

    @pytest.mark.asyncio
    async def test_list_subclasses_response_model(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test response conforms to EquipmentSubclassList schema."""
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/Centrifugation/subclasses"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
        for item in data["items"]:
            assert isinstance(item, str)


class TestGetClassSubclassMap:
    """Tests for GET /{submodule}/class-subclass-map endpoint."""

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_success(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test successfully getting class-subclass map."""
        response = await client.get(
            "/api/v1/power-factors/scientific/class-subclass-map"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], dict)
        assert len(data["items"]) == 3

        # Centrifugation has 2 subclasses
        assert "Centrifugation" in data["items"]
        assert len(data["items"]["Centrifugation"]) == 2
        assert "Ultra centrifuges" in data["items"]["Centrifugation"]
        assert "Microcentrifuges" in data["items"]["Centrifugation"]

        # Microscopy has no subclasses
        assert "Microscopy" in data["items"]
        assert data["items"]["Microscopy"] == []

        # Cell culture / Incubation has 1 subclass
        assert "Cell culture / Incubation" in data["items"]
        assert len(data["items"]["Cell culture / Incubation"]) == 1

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_it_submodule(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test getting map for IT submodule."""
        response = await client.get("/api/v1/power-factors/it/class-subclass-map")

        assert response.status_code == 200
        data = response.json()
        assert "Desktop Computers" in data["items"]
        assert data["items"]["Desktop Computers"] == ["Workstation"]

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_empty(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test getting map for submodule with no data."""
        response = await client.get(
            "/api/v1/power-factors/nonexistent/class-subclass-map"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == {}

    @pytest.mark.asyncio
    async def test_get_class_subclass_map_response_model(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test response conforms to EquipmentSubclassMap schema."""
        response = await client.get(
            "/api/v1/power-factors/scientific/class-subclass-map"
        )

        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], dict)
        for class_name, subclasses in data["items"].items():
            assert isinstance(class_name, str)
            assert isinstance(subclasses, list)
            for subclass in subclasses:
                assert isinstance(subclass, str)


class TestGetPowerFactor:
    """Tests for GET /{submodule}/classes/{equipment_class}/power endpoint."""

    @pytest.mark.asyncio
    async def test_get_power_factor_exact_match(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test getting power factor with exact subclass match."""
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/Centrifugation/power",
            params={"sub_class": "Ultra centrifuges"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["submodule"] == "scientific"
        assert data["equipment_class"] == "Centrifugation"
        assert data["sub_class"] == "Ultra centrifuges"
        assert data["active_power_w"] == 1300.0
        assert data["standby_power_w"] == 130.0

    @pytest.mark.asyncio
    async def test_get_power_factor_fallback_to_class(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test fallback to class-level when subclass not found."""
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/Centrifugation/power",
            params={"sub_class": "NonexistentSubclass"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["submodule"] == "scientific"
        assert data["equipment_class"] == "Centrifugation"
        assert data["sub_class"] is None  # Class-level fallback
        assert data["active_power_w"] == 800.0
        assert data["standby_power_w"] == 80.0

    @pytest.mark.asyncio
    async def test_get_power_factor_no_subclass_param(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test getting power factor without subclass parameter."""
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/Microscopy/power"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["submodule"] == "scientific"
        assert data["equipment_class"] == "Microscopy"
        assert data["sub_class"] is None
        assert data["active_power_w"] == 500.0

    @pytest.mark.asyncio
    async def test_get_power_factor_path_normalization(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test path parameter normalization for slashes."""
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/Cell culture/Incubation/power",
            params={"sub_class": "CO2 incubators"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["equipment_class"] == "Cell culture / Incubation"
        assert data["sub_class"] == "CO2 incubators"
        assert data["active_power_w"] == 250.0

    @pytest.mark.asyncio
    async def test_get_power_factor_not_found(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test getting power factor when no match exists returns None."""
        response = await client.get(
            "/api/v1/power-factors/nonexistent/classes/Nonexistent/power"
        )

        assert response.status_code == 200
        # FastAPI returns null for None values
        assert response.json() is None

    @pytest.mark.asyncio
    async def test_get_power_factor_response_model(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test response conforms to PowerFactorOut schema."""
        response = await client.get(
            "/api/v1/power-factors/scientific/classes/Centrifugation/power",
            params={"sub_class": "Ultra centrifuges"},
        )

        assert response.status_code == 200
        data = response.json()
        # Verify all required fields are present
        assert "submodule" in data
        assert "equipment_class" in data
        assert "sub_class" in data
        assert "active_power_w" in data
        assert "standby_power_w" in data
        # Verify types
        assert isinstance(data["submodule"], str)
        assert isinstance(data["equipment_class"], str)
        assert isinstance(data["active_power_w"], (int, float))
        assert isinstance(data["standby_power_w"], (int, float))

    @pytest.mark.asyncio
    async def test_get_power_factor_with_it_equipment(
        self,
        client: AsyncClient,
        sample_power_factors,
    ):
        """Test getting power factor for IT equipment."""
        response = await client.get(
            "/api/v1/power-factors/it/classes/Desktop Computers/power",
            params={"sub_class": "Workstation"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["submodule"] == "it"
        assert data["equipment_class"] == "Desktop Computers"
        assert data["sub_class"] == "Workstation"
        assert data["active_power_w"] == 200.0
        assert data["standby_power_w"] == 20.0
