"""Tests for unit_provider.py — providers, factory, and mapping logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.models.user import UserProvider
from app.providers.unit_provider import (
    AccredUnitProvider,
    DefaultUnitProvider,
    TestUnitProvider,
    get_unit_provider,
)


# ---------------------------------------------------------------------------
# AccredUnitProvider.map_api_unit
# ---------------------------------------------------------------------------
class TestAccredMapApiUnit:
    def _make_provider(self):
        with patch("app.providers.unit_provider.settings") as mock_settings:
            mock_settings.ACCRED_API_URL = "https://api.example.com"
            mock_settings.ACCRED_API_USERNAME = "user"
            mock_settings.ACCRED_API_KEY = "key"
            return AccredUnitProvider()

    def _raw_unit(self, **overrides):
        base = {
            "id": 42,
            "cf": "LMSC",
            "name": "Lab of Molecular Sim",
            "labelfr": "Labo sim mol",
            "labelen": "Mol Sim Lab",
            "level": 4,
            "parentid": 10,
            "level4cf": "STI",
            "ancestors": ["1", "5", "10"],
            "pathcf": "EPFL STI LMSC",
            "path": "EPFL > STI > LMSC",
            "unittypeid": 3,
            "unittype": {"label": "Laboratory"},
            "responsibleid": "12345",
            "enddate": "0001-01-01T00:00:00Z",
        }
        base.update(overrides)
        return base

    def test_basic_mapping(self):
        provider = self._make_provider()
        unit = provider.map_api_unit(self._raw_unit())
        assert unit.institutional_code == "42"
        assert unit.institutional_id == "LMSC"
        assert unit.name == "Lab of Molecular Sim"
        assert unit.label_fr == "Labo sim mol"
        assert unit.label_en == "Mol Sim Lab"
        assert unit.level == 4
        assert unit.parent_institutional_code == "10"
        assert unit.parent_institutional_id == "STI"
        assert unit.path_institutional_code == "1 5 10 42"
        assert unit.path_institutional_id == "EPFL STI LMSC"
        assert unit.path_name == "EPFL > STI > LMSC"
        assert unit.unit_type_id == 3
        assert unit.unit_type_label == "Laboratory"
        assert unit.principal_user_institutional_id == "12345"
        assert unit.is_active is True
        assert unit.provider == UserProvider.ACCRED

    def test_inactive_unit(self):
        provider = self._make_provider()
        unit = provider.map_api_unit(self._raw_unit(enddate="2024-12-31T00:00:00Z"))
        assert unit.is_active is False

    def test_cf_zero_maps_to_none(self):
        provider = self._make_provider()
        unit = provider.map_api_unit(self._raw_unit(cf="0"))
        assert unit.institutional_id is None

    def test_cf_none_maps_to_none(self):
        provider = self._make_provider()
        unit = provider.map_api_unit(self._raw_unit(cf=None))
        assert unit.institutional_id is None

    def test_level1_no_parent_institutional_id(self):
        provider = self._make_provider()
        unit = provider.map_api_unit(self._raw_unit(level=1))
        assert unit.parent_institutional_id is None

    def test_no_unittype(self):
        provider = self._make_provider()
        unit = provider.map_api_unit(self._raw_unit(unittype=None))
        assert unit.unit_type_label is None

    def test_no_parentid(self):
        provider = self._make_provider()
        unit = provider.map_api_unit(self._raw_unit(parentid=None))
        assert unit.parent_institutional_code is None

    def test_missing_optional_fields(self):
        provider = self._make_provider()
        raw = {
            "id": 1,
            "cf": None,
            "name": "Root",
            "level": 1,
            "ancestors": [],
        }
        unit = provider.map_api_unit(raw)
        assert unit.name == "Root"
        assert unit.label_fr is None
        assert unit.path_name is None


# ---------------------------------------------------------------------------
# AccredUnitProvider.get_units (with httpx mock)
# ---------------------------------------------------------------------------
class TestAccredGetUnits:
    def _make_provider(self):
        with patch("app.providers.unit_provider.settings") as mock_settings:
            mock_settings.ACCRED_API_URL = "https://api.example.com"
            mock_settings.ACCRED_API_USERNAME = "user"
            mock_settings.ACCRED_API_KEY = "key"
            return AccredUnitProvider()

    @pytest.mark.asyncio
    async def test_get_units_success(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "units": [
                {
                    "id": 1,
                    "cf": "LMSC",
                    "name": "Test Unit",
                    "level": 4,
                    "parentid": 10,
                    "ancestors": ["1"],
                    "enddate": "0001-01-01T00:00:00Z",
                }
            ]
        }

        with patch("app.providers.unit_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            units = await provider.get_units(unit_ids=["LMSC"])
            assert len(units) == 1
            assert units[0].name == "Test Unit"

    @pytest.mark.asyncio
    async def test_get_units_empty(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"units": []}

        with patch("app.providers.unit_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            units = await provider.get_units(unit_ids=["NONEXIST"])
            assert units == []

    @pytest.mark.asyncio
    async def test_get_units_not_configured(self):
        with patch("app.providers.unit_provider.settings") as mock_settings:
            mock_settings.ACCRED_API_URL = ""
            mock_settings.ACCRED_API_USERNAME = ""
            mock_settings.ACCRED_API_KEY = ""
            provider = AccredUnitProvider()
            units = await provider.get_units()
            assert units == []

    @pytest.mark.asyncio
    async def test_get_units_http_error(self):
        provider = self._make_provider()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=mock_response
        )

        with patch("app.providers.unit_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with pytest.raises(httpx.HTTPStatusError):
                await provider.get_units(unit_ids=["LMSC"])


# ---------------------------------------------------------------------------
# AccredUnitProvider.fetch_all_units
# ---------------------------------------------------------------------------
class TestAccredFetchAllUnits:
    @pytest.mark.asyncio
    async def test_fetch_all_units_not_configured(self):
        with patch("app.providers.unit_provider.settings") as mock_settings:
            mock_settings.ACCRED_API_URL = ""
            mock_settings.ACCRED_API_USERNAME = ""
            mock_settings.ACCRED_API_KEY = ""
            provider = AccredUnitProvider()
            units, users = await provider.fetch_all_units()
            assert units == []
            assert users == []

    @pytest.mark.asyncio
    async def test_fetch_all_units_single_page(self):
        with patch("app.providers.unit_provider.settings") as mock_settings:
            mock_settings.ACCRED_API_URL = "https://api.example.com"
            mock_settings.ACCRED_API_USERNAME = "user"
            mock_settings.ACCRED_API_KEY = "key"
            provider = AccredUnitProvider()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "count": 1,
            "units": [
                {
                    "id": 1,
                    "name": "U1",
                    "responsible": {
                        "id": "R1",
                        "email": "r1@test.com",
                    },
                }
            ],
        }

        with patch("app.providers.unit_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            units, users = await provider.fetch_all_units()
            assert len(units) == 1
            assert len(users) == 1
            assert users[0]["email"] == "r1@test.com"

    @pytest.mark.asyncio
    async def test_fetch_all_units_deduplicates_users(self):
        with patch("app.providers.unit_provider.settings") as mock_settings:
            mock_settings.ACCRED_API_URL = "https://api.example.com"
            mock_settings.ACCRED_API_USERNAME = "user"
            mock_settings.ACCRED_API_KEY = "key"
            provider = AccredUnitProvider()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        responsible = {"id": "R1", "email": "r1@test.com"}
        mock_response.json.return_value = {
            "count": 2,
            "units": [
                {"id": 1, "name": "U1", "responsible": responsible},
                {"id": 2, "name": "U2", "responsible": responsible},
            ],
        }

        with patch("app.providers.unit_provider.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            units, users = await provider.fetch_all_units()
            assert len(units) == 2
            assert len(users) == 1  # deduplicated


# ---------------------------------------------------------------------------
# DefaultUnitProvider.get_units (with real async db)
# ---------------------------------------------------------------------------
class TestDefaultUnitProvider:
    @pytest.mark.asyncio
    async def test_get_all_units(self, db_session, make_unit):
        _u1 = await make_unit(db_session, name="Unit A")
        _u2 = await make_unit(db_session, name="Unit B")

        provider = DefaultUnitProvider(db_session)
        units = await provider.get_units()
        assert len(units) == 2

    @pytest.mark.asyncio
    async def test_get_units_filtered(self, db_session, make_unit):
        u1 = await make_unit(db_session, name="Unit A")
        _u2 = await make_unit(db_session, name="Unit B")

        provider = DefaultUnitProvider(db_session)
        units = await provider.get_units(unit_ids=[u1.id])
        assert len(units) == 1
        assert units[0].name == "Unit A"

    @pytest.mark.asyncio
    async def test_get_units_empty_db(self, db_session):
        provider = DefaultUnitProvider(db_session)
        units = await provider.get_units()
        assert units == []


# ---------------------------------------------------------------------------
# TestUnitProvider
# ---------------------------------------------------------------------------
class TestTestUnitProvider:
    @pytest.mark.asyncio
    async def test_returns_all(self):
        provider = TestUnitProvider()
        units = await provider.get_units()
        assert len(units) > 0

    @pytest.mark.asyncio
    async def test_filter_by_id(self):
        provider = TestUnitProvider()
        all_units = await provider.get_units()
        if all_units:
            target_id = all_units[0].institutional_id
            filtered = await provider.get_units(unit_ids=[target_id])
            assert all(u.institutional_id == target_id for u in filtered)

    @pytest.mark.asyncio
    async def test_filter_nonexistent(self):
        provider = TestUnitProvider()
        units = await provider.get_units(unit_ids=["NONEXISTENT_ID_XYZ"])
        assert units == []


# ---------------------------------------------------------------------------
# get_unit_by_id (base class method)
# ---------------------------------------------------------------------------
class TestGetUnitById:
    @pytest.mark.asyncio
    async def test_found(self):
        provider = TestUnitProvider()
        all_units = await provider.get_units()
        if all_units:
            target = all_units[0]
            result = await provider.get_unit_by_id(target.institutional_id)
            assert result is not None
            assert result.institutional_id == target.institutional_id

    @pytest.mark.asyncio
    async def test_not_found(self):
        provider = TestUnitProvider()
        result = await provider.get_unit_by_id("NONEXISTENT_XYZ")
        assert result is None


# ---------------------------------------------------------------------------
# get_unit_provider factory
# ---------------------------------------------------------------------------
class TestGetUnitProvider:
    def test_default_requires_session(self):
        with pytest.raises(ValueError, match="requires a database session"):
            get_unit_provider(UserProvider.DEFAULT, db_session=None)

    def test_default_with_session(self):
        mock_db = MagicMock()
        provider = get_unit_provider(UserProvider.DEFAULT, db_session=mock_db)
        assert isinstance(provider, DefaultUnitProvider)

    def test_accred(self):
        provider = get_unit_provider(UserProvider.ACCRED)
        assert isinstance(provider, AccredUnitProvider)

    def test_test_provider(self):
        provider = get_unit_provider(UserProvider.TEST)
        assert isinstance(provider, TestUnitProvider)

    def test_unknown_falls_back_to_default(self):
        mock_db = MagicMock()
        provider = get_unit_provider(999, db_session=mock_db)
        assert isinstance(provider, DefaultUnitProvider)

    def test_unknown_without_session_raises(self):
        with pytest.raises(ValueError):
            get_unit_provider(999, db_session=None)

    def test_none_uses_settings(self):
        with patch("app.providers.unit_provider.settings") as mock_settings:
            mock_settings.PROVIDER_PLUGIN = UserProvider.TEST
            provider = get_unit_provider(None)
            assert isinstance(provider, TestUnitProvider)
