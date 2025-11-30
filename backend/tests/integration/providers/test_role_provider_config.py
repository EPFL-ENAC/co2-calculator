from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.models.user import Role, RoleName
from app.providers.role_provider import get_role_provider

# ============================================================================
# Integration Tests
# ============================================================================


class TestRoleProviderIntegration:
    """Integration tests for role provider system."""

    @pytest.mark.asyncio
    async def test_default_provider_full_workflow(self):
        """Test complete workflow with DefaultRoleProvider."""
        with patch("app.providers.role_provider.settings") as mock_settings:
            mock_settings.ROLE_PROVIDER_PLUGIN = "default"

            provider = get_role_provider()
            userinfo = {
                "email": "user@epfl.ch",
                "roles": [
                    "co2.user.std@unit:100",
                    "co2.user.principal@unit:200",
                    "co2.backoffice.admin@global",
                ],
            }

            roles, _, _ = await provider.get_roles(userinfo, 123456)

            assert len(roles) == 3
            assert all(isinstance(role, Role) for role in roles)

    @pytest.mark.asyncio
    async def test_accred_provider_full_workflow(self):
        """Test complete workflow with AccredRoleProvider."""
        with patch("app.providers.role_provider.settings") as mock_settings:
            mock_settings.ROLE_PROVIDER_PLUGIN = "accred"
            mock_settings.ACCRED_API_URL = "https://api-test.epfl.ch"
            mock_settings.ACCRED_API_USERNAME = "user"
            mock_settings.ACCRED_API_KEY = "key"

            mock_response = {
                "authorizations": [
                    {
                        "name": "co2.user.std",
                        "state": "active",
                        "accredunitid": "100",
                    }
                ]
            }

            provider = get_role_provider()

            with patch(
                "app.providers.role_provider.httpx.AsyncClient"
            ) as mock_client_class:
                mock_client = AsyncMock()
                mock_response_obj = Mock()
                mock_response_obj.json.return_value = mock_response
                mock_client.__aenter__.return_value = mock_client
                mock_client.get.return_value = mock_response_obj

                mock_client_class.return_value = mock_client

                roles, _, _ = await provider.get_roles({}, 123456)

            assert len(roles) == 1
            assert roles[0].role == RoleName.CO2_USER_STD
