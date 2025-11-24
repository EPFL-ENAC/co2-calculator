"""Unit and integration tests for role provider plugin system.

Tests cover both DefaultRoleProvider and AccredRoleProvider with 100% coverage.
"""

from typing import Any, Dict
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from app.core.role_provider import (
    AccredRoleProvider,
    DefaultRoleProvider,
    get_role_provider,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_settings():
    """Fixture providing mock settings."""
    settings = Mock()
    settings.ACCRED_API_URL = "https://api.epfl.ch"
    settings.ACCRED_API_USERNAME = "test_user"
    settings.ACCRED_API_KEY = "test_key"
    settings.ROLE_PROVIDER_PLUGIN = "default"
    return settings


@pytest.fixture
def mock_logger():
    """Fixture providing mock logger."""
    return Mock()


@pytest.fixture
def sample_userinfo() -> Dict[str, Any]:
    """Fixture providing sample userinfo dict."""
    return {
        "email": "user@epfl.ch",
        "sciper": 352707,
        "roles": [
            "co2.user.std@unit:12345",
            "co2.user.principal@unit:12345",
            "co2.backoffice.admin@global",
        ],
    }


@pytest.fixture
def sample_sciper() -> int:
    """Fixture providing sample SCIPER number."""
    return 352707


# ============================================================================
# DefaultRoleProvider Tests
# ============================================================================


class TestDefaultRoleProvider:
    """Test suite for DefaultRoleProvider."""

    @pytest.mark.asyncio
    async def test_parse_roles_with_unit_scope(self, sample_userinfo, sample_sciper):
        """Test parsing roles with unit scope."""
        provider = DefaultRoleProvider()
        roles = await provider.get_roles(sample_userinfo, sample_sciper)

        assert len(roles) == 3
        assert roles[0] == {"role": "co2.user.std", "on": {"unit": "12345"}}
        assert roles[1] == {"role": "co2.user.principal", "on": {"unit": "12345"}}
        assert roles[2] == {"role": "co2.backoffice.admin", "on": "global"}

    @pytest.mark.asyncio
    async def test_parse_roles_with_global_scope(self, sample_sciper):
        """Test parsing roles with global scope."""
        userinfo = {
            "email": "admin@epfl.ch",
            "roles": ["co2.backoffice.admin@global"],
        }
        provider = DefaultRoleProvider()
        roles = await provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1
        assert roles[0] == {"role": "co2.backoffice.admin", "on": "global"}

    @pytest.mark.asyncio
    async def test_parse_roles_no_roles_in_jwt(self, sample_sciper):
        """Test handling of missing roles in JWT."""
        userinfo = {"email": "user@epfl.ch"}
        provider = DefaultRoleProvider()
        roles = await provider.get_roles(userinfo, sample_sciper)

        assert roles == []

    @pytest.mark.asyncio
    async def test_parse_roles_empty_roles_list(self, sample_sciper):
        """Test handling of empty roles list."""
        userinfo = {"email": "user@epfl.ch", "roles": []}
        provider = DefaultRoleProvider()
        roles = await provider.get_roles(userinfo, sample_sciper)

        assert roles == []

    @pytest.mark.asyncio
    async def test_skip_non_string_role(self, sample_sciper):
        """Test that non-string roles are skipped."""
        userinfo = {
            "email": "user@epfl.ch",
            "roles": [
                123,  # Invalid: not a string
                "co2.user.std@unit:12345",
            ],
        }
        provider = DefaultRoleProvider()
        roles = await provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1
        assert roles[0] == {"role": "co2.user.std", "on": {"unit": "12345"}}

    @pytest.mark.asyncio
    async def test_skip_role_without_scope(self, sample_sciper):
        """Test that roles without @ scope are skipped."""
        userinfo = {
            "email": "user@epfl.ch",
            "roles": [
                "co2.user.std",  # Invalid: no @
                "co2.user.std@unit:12345",
            ],
        }
        provider = DefaultRoleProvider()
        roles = await provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1
        assert roles[0] == {"role": "co2.user.std", "on": {"unit": "12345"}}

    @pytest.mark.asyncio
    async def test_skip_role_with_invalid_scope_format(self, sample_sciper):
        """Test that roles with invalid scope format are skipped."""
        userinfo = {
            "email": "user@epfl.ch",
            "roles": [
                "co2.user.std@invalid",  # Invalid: no colon in scope
                "co2.user.std@unit:12345",
            ],
        }
        provider = DefaultRoleProvider()
        roles = await provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1
        assert roles[0] == {"role": "co2.user.std", "on": {"unit": "12345"}}

    @pytest.mark.asyncio
    async def test_parse_role_with_whitespace(self, sample_sciper):
        """Test that whitespace in roles is trimmed."""
        userinfo = {
            "email": "user@epfl.ch",
            "roles": [" co2.user.std @ unit : 12345 "],
        }
        provider = DefaultRoleProvider()
        roles = await provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1
        assert roles[0] == {"role": "co2.user.std", "on": {"unit": "12345"}}

    @pytest.mark.asyncio
    async def test_parse_multiple_roles_with_different_units(self, sample_sciper):
        """Test parsing multiple roles with different unit scopes."""
        userinfo = {
            "email": "user@epfl.ch",
            "roles": [
                "co2.user.std@unit:12345",
                "co2.user.principal@unit:67890",
                "co2.user.secondary@unit:11111",
            ],
        }
        provider = DefaultRoleProvider()
        roles = await provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 3
        assert roles[0]["on"] == {"unit": "12345"}
        assert roles[1]["on"] == {"unit": "67890"}
        assert roles[2]["on"] == {"unit": "11111"}


# ============================================================================
# AccredRoleProvider Tests
# ============================================================================


class TestAccredRoleProvider:
    """Test suite for AccredRoleProvider."""

    @pytest.fixture
    def accred_provider(self):
        """Fixture providing an AccredRoleProvider instance."""
        with patch("app.core.role_provider.settings") as mock_settings:
            mock_settings.ACCRED_API_URL = "https://api.epfl.ch"
            mock_settings.ACCRED_API_USERNAME = "test_user"
            mock_settings.ACCRED_API_KEY = "test_key"
            provider = AccredRoleProvider()
        return provider

    @pytest.mark.asyncio
    async def test_accred_fetch_roles_with_unit_authorizations(
        self, accred_provider, sample_sciper
    ):
        """Test fetching roles from Accred API with unit authorizations."""
        mock_response = {
            "authorizations": [
                {
                    "name": "co2.user.std",
                    "state": "active",
                    "accredunitid": "12345",
                },
                {
                    "name": "co2.user.principal",
                    "state": "active",
                    "accredunitid": "67890",
                },
            ]
        }

        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.json = Mock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response_obj

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 2
        assert roles[0] == {"role": "co2.user.std", "on": {"unit": "12345"}}
        assert roles[1] == {"role": "co2.user.principal", "on": {"unit": "67890"}}

    @pytest.mark.asyncio
    async def test_accred_fetch_roles_with_global_admin(
        self, accred_provider, sample_sciper
    ):
        """Test fetching global admin role from Accred API."""
        mock_response = {
            "authorizations": [
                {
                    "name": "co2.backoffice.admin",
                    "state": "active",
                    "accredunitid": "12345",
                }
            ]
        }

        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.json = Mock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response_obj

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1
        assert roles[0] == {"role": "co2.backoffice.admin", "on": "global"}

    @pytest.mark.asyncio
    async def test_accred_fetch_roles_with_backoffice_std(
        self, accred_provider, sample_sciper
    ):
        """Test fetching backoffice.std role with affiliation scope."""
        mock_response = {
            "authorizations": [
                {
                    "name": "co2.backoffice.std",
                    "state": "active",
                    "accredunitid": "12345",
                    "reason": {"resource": {"sortpath": "Engineering"}},
                }
            ]
        }

        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.json = Mock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response_obj

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1
        assert roles[0] == {
            "role": "co2.backoffice.std",
            "on": {"affiliation": "Engineering"},
        }

    @pytest.mark.asyncio
    async def test_accred_no_authorizations_found(self, accred_provider, sample_sciper):
        """Test handling of empty authorizations list."""
        mock_response = {"authorizations": []}

        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.json = Mock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response_obj

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert roles == []

    @pytest.mark.asyncio
    async def test_accred_skip_non_co2_authorization(
        self, accred_provider, sample_sciper
    ):
        """Test that non-co2 authorizations are skipped."""
        mock_response = {
            "authorizations": [
                {
                    "name": "other.role",
                    "state": "active",
                    "accredunitid": "12345",
                },
                {
                    "name": "co2.user.std",
                    "state": "active",
                    "accredunitid": "12345",
                },
            ]
        }

        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.json = Mock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response_obj

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1
        assert roles[0]["role"] == "co2.user.std"

    @pytest.mark.asyncio
    async def test_accred_skip_inactive_authorization(
        self, accred_provider, sample_sciper
    ):
        """Test that inactive authorizations are skipped."""
        mock_response = {
            "authorizations": [
                {
                    "name": "co2.user.std",
                    "state": "inactive",
                    "accredunitid": "12345",
                },
                {
                    "name": "co2.user.std",
                    "state": "active",
                    "accredunitid": "12345",
                },
            ]
        }

        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.json = Mock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response_obj

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1

    @pytest.mark.asyncio
    async def test_accred_skip_authorization_without_accredunitid(
        self, accred_provider, sample_sciper
    ):
        """Test that authorizations without accredunitid are skipped."""
        mock_response = {
            "authorizations": [
                {
                    "name": "co2.user.std",
                    "state": "active",
                },
                {
                    "name": "co2.user.std",
                    "state": "active",
                    "accredunitid": "12345",
                },
            ]
        }

        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.json = Mock(return_value=mock_response)
            mock_response_obj.raise_for_status = AsyncMock()
            mock_client.__aenter__.return_value = mock_client
            mock_client.get.return_value = mock_response_obj

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert len(roles) == 1

    @pytest.mark.asyncio
    async def test_accred_http_status_error(self, accred_provider, sample_sciper):
        """Test handling of HTTP status errors from Accred API."""
        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response_obj = AsyncMock()
            mock_response_obj.status_code = 401

            error = httpx.HTTPStatusError(
                "Unauthorized",
                request=Mock(),
                response=mock_response_obj,
            )

            mock_client.__aenter__.return_value = mock_client
            mock_client.get.side_effect = error

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert roles == []

    @pytest.mark.asyncio
    async def test_accred_request_error(self, accred_provider, sample_sciper):
        """Test handling of request errors from Accred API."""
        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            error = httpx.RequestError("Connection error")

            mock_client.__aenter__.return_value = mock_client
            mock_client.get.side_effect = error

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert roles == []

    @pytest.mark.asyncio
    async def test_accred_unexpected_error(self, accred_provider, sample_sciper):
        """Test handling of unexpected errors from Accred API."""
        userinfo = {}

        with patch("app.core.role_provider.httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            error = ValueError("Unexpected error")

            mock_client.__aenter__.return_value = mock_client
            mock_client.get.side_effect = error

            mock_client_class.return_value = mock_client

            roles = await accred_provider.get_roles(userinfo, sample_sciper)

        assert roles == []

    def test_accred_missing_credentials(self):
        """Test AccredRoleProvider initialization with missing credentials."""
        with patch("app.core.role_provider.settings") as mock_settings:
            mock_settings.ACCRED_API_URL = None
            mock_settings.ACCRED_API_USERNAME = "user"
            mock_settings.ACCRED_API_KEY = "key"

            provider = AccredRoleProvider()
            assert provider.api_url is None

    @pytest.mark.asyncio
    async def test_accred_missing_credentials_get_roles(self):
        """Test get_roles returns empty list when credentials are missing."""
        with patch("app.core.role_provider.settings") as mock_settings:
            mock_settings.ACCRED_API_URL = None
            mock_settings.ACCRED_API_USERNAME = "user"
            mock_settings.ACCRED_API_KEY = "key"

            provider = AccredRoleProvider()
            roles = await provider.get_roles({}, 123456)

        assert roles == []


# ============================================================================
# Factory Function Tests
# ============================================================================


class TestGetRoleProvider:
    """Test suite for get_role_provider factory function."""

    def test_get_default_role_provider(self):
        """Test that DefaultRoleProvider is returned for 'default' type."""
        with patch("app.core.role_provider.settings") as mock_settings:
            mock_settings.ROLE_PROVIDER_PLUGIN = "default"

            provider = get_role_provider()

            assert isinstance(provider, DefaultRoleProvider)

    def test_get_accred_role_provider(self):
        """Test that AccredRoleProvider is returned for 'accred' type."""
        with patch("app.core.role_provider.settings") as mock_settings:
            mock_settings.ROLE_PROVIDER_PLUGIN = "accred"
            mock_settings.ACCRED_API_URL = "https://api.epfl.ch"
            mock_settings.ACCRED_API_USERNAME = "user"
            mock_settings.ACCRED_API_KEY = "key"

            provider = get_role_provider()

            assert isinstance(provider, AccredRoleProvider)

    def test_get_unknown_role_provider_fallback_to_default(self):
        """Test that unknown provider type falls back to DefaultRoleProvider."""
        with patch("app.core.role_provider.settings") as mock_settings:
            mock_settings.ROLE_PROVIDER_PLUGIN = "unknown"

            provider = get_role_provider()

            assert isinstance(provider, DefaultRoleProvider)
