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
            mock_settings.PROVIDER_PLUGIN = "default"

            provider = get_role_provider()
            userinfo = {
                "email": "user@epfl.ch",
                "roles": [
                    f"{RoleName.CO2_USER_STD.value}@unit:100",
                    f"{RoleName.CO2_USER_PRINCIPAL.value}@unit:200",
                    f"{RoleName.CO2_SUPERADMIN.value}@global",
                ],
            }

            roles = await provider.get_roles(userinfo)

            assert len(roles) == 3
            assert all(isinstance(role, Role) for role in roles)

    @pytest.mark.asyncio
    async def test_accred_provider_full_workflow(self):
        """Test complete workflow with AccredRoleProvider."""
        with patch("app.providers.role_provider.settings") as mock_settings:
            mock_settings.PROVIDER_PLUGIN = "accred"
            mock_settings.ACCRED_API_URL = "https://api-test.epfl.ch"
            mock_settings.ACCRED_API_USERNAME = "user"
            mock_settings.ACCRED_API_KEY = "key"

            mock_response = {
                "authorizations": [
                    {
                        "name": f"{RoleName.CO2_USER_STD.value}",
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

                roles = await provider.get_roles({"uniqueid": 123456})

            assert len(roles) == 1
            assert roles[0].role == RoleName.CO2_USER_STD
