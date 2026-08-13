"""Unit tests for core policy module - authorization policy evaluation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.core.policy import (
    _get_module_permission_path,
    check_module_permission,
    check_module_permission_for_report,
    is_module_permitted,
    plan_is_visible_to,
    query_policy,
    require_plan_access,
    require_plan_scope_for_report,
)
from app.models.user import GlobalScope, OwnScope, Role, RoleName, UnitScope


class TestGetModulePermissionPath:
    """Tests for _get_module_permission_path function."""

    def test_professional_travel_module(self):
        """Test mapping for professional-travel module."""
        result = _get_module_permission_path("professional-travel")
        assert result == "modules.professional_travel"

    def test_equipment_module(self):
        """Test mapping for equipment module."""
        result = _get_module_permission_path("equipment")
        assert result == "modules.equipment"

    def test_buildings_module(self):
        """Test mapping for buildings module."""
        result = _get_module_permission_path("buildings")
        assert result == "modules.buildings"

    def test_purchase_module(self):
        """Test mapping for purchase module."""
        result = _get_module_permission_path("purchase")
        assert result == "modules.purchase"

    def test_research_facilities_module(self):
        """Test mapping for research-facilities module."""
        result = _get_module_permission_path("research-facilities")
        assert result == "modules.research_facilities"

    def test_external_cloud_and_ai_module(self):
        """Test mapping for external-cloud-and-ai module."""
        result = _get_module_permission_path("external-cloud-and-ai")
        assert result == "modules.external_cloud_and_ai"

    def test_my_lab_module(self):
        """Test mapping for my-lab module (headcount)."""
        result = _get_module_permission_path("my-lab")
        assert result == "modules.headcount"

    def test_processes_module(self):
        """Test mapping for processes module."""
        result = _get_module_permission_path("process-emissions")
        assert result == "modules.process_emissions"

    def test_unknown_module_returns_default_path(self):
        """Test that unknown module ID returns default path."""
        result = _get_module_permission_path("unknown-module")
        assert result == "modules.unknown_module"

    def test_empty_string_returns_none(self):
        """Test that empty string module ID returns None."""
        result = _get_module_permission_path("")
        assert result is None

    def test_case_insensitive_module_id(self):
        """Test that module ID is case-insensitive."""
        # Mixed case should still map to the correct path
        result = _get_module_permission_path("Professional-Travel")
        assert (
            result == "modules.professional_travel"
        )  # Still maps to correct path due to lower() in mapping


class TestCheckModulePermission:
    """Tests for check_module_permission async function."""

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_allow(self, mock_query_policy):
        """Test check_module_permission when permission is granted."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [
            Role(role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id="123"))
        ]

        # Mock policy allows access
        mock_query_policy.return_value = {
            "allow": True,
            "reason": "Permission granted",
        }

        # Should not raise exception
        await check_module_permission(user, "professional-travel", "view")

        # Verify query_policy was called correctly
        mock_query_policy.assert_awaited_once()
        call_args = mock_query_policy.call_args
        assert call_args[0][0] == "authz/permission/check"
        assert call_args[0][1]["path"] == "modules.professional_travel"
        assert call_args[0][1]["action"] == "view"

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_deny(self, mock_query_policy):
        """Test check_module_permission when permission is denied."""
        user = MagicMock()
        user.id = "user-456"
        user.email = "test@example.com"
        user.roles = []

        # Mock policy denies access
        mock_query_policy.return_value = {
            "allow": False,
            "reason": "Insufficient permissions",
        }

        # Should raise HTTPException
        with pytest.raises(HTTPException) as exc_info:
            await check_module_permission(user, "equipment", "edit")

        assert exc_info.value.status_code == 403
        assert "Permission denied" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_check_module_permission_no_path_required(self):
        """Test check_module_permission for module without permission path."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = []

        # Module without permission requirement must not be allowed by default
        result = await is_module_permitted(user, "unknown-module", "view")
        assert result is False  # No permission specified, so access is denied

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_view_action(self, mock_query_policy):
        """Test check_module_permission with view action."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [
            Role(role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id="123"))
        ]

        mock_query_policy.return_value = {"allow": True}

        await check_module_permission(user, "buildings", "view")

        call_args = mock_query_policy.call_args
        assert call_args[0][1]["action"] == "view"

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_edit_action(self, mock_query_policy):
        """Test check_module_permission with edit action."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [
            Role(role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id="123"))
        ]

        mock_query_policy.return_value = {"allow": True}

        await check_module_permission(user, "purchase", "edit")

        call_args = mock_query_policy.call_args
        assert call_args[0][1]["action"] == "edit"

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_user_without_roles(self, mock_query_policy):
        """Test check_module_permission for user with None roles."""
        user = MagicMock()
        user.id = "user-789"
        user.email = "noroles@example.com"
        user.roles = None

        mock_query_policy.return_value = {
            "allow": False,
            "reason": "No roles assigned",
        }

        with pytest.raises(HTTPException) as exc_info:
            await check_module_permission(user, "professional-travel", "view")

        assert exc_info.value.status_code == 403

        # Verify roles were passed as empty list
        call_args = mock_query_policy.call_args
        assert call_args[0][1]["user"]["roles"] == []

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_different_modules(self, mock_query_policy):
        """Test check_module_permission with various modules."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [
            Role(role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id="123"))
        ]

        mock_query_policy.return_value = {"allow": True}

        modules = [
            ("professional-travel", "modules.professional_travel"),
            ("equipment", "modules.equipment"),
            ("my-lab", "modules.headcount"),
            ("external-cloud-and-ai", "modules.external_cloud_and_ai"),
        ]

        for module_id, expected_path in modules:
            await check_module_permission(user, module_id, "view")

            # Verify correct permission path was used
            call_args = mock_query_policy.call_args
            assert call_args[0][1]["path"] == expected_path

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_forwards_institutional_id(
        self, mock_query_policy
    ):
        """institutional_id kwarg must reach the policy via input_data so the
        scoped permission key (modules.X/iid) can be matched.
        """
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [
            Role(
                role=RoleName.CO2_USER_PRINCIPAL,
                on=UnitScope(institutional_id="0184"),
            )
        ]

        mock_query_policy.return_value = {"allow": True}

        await check_module_permission(
            user, "headcount", "view", institutional_id="0184"
        )

        call_args = mock_query_policy.call_args
        assert call_args[0][1]["path"] == "modules.headcount"
        assert call_args[0][1]["institutional_id"] == "0184"
        assert call_args[0][1]["any_scope"] is False

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_forwards_any_scope(self, mock_query_policy):
        """any_scope kwarg must reach the policy via input_data (taxonomy path)."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = []

        mock_query_policy.return_value = {"allow": True}

        await check_module_permission(user, "headcount", "view", any_scope=True)

        call_args = mock_query_policy.call_args
        assert call_args[0][1]["any_scope"] is True
        assert call_args[0][1]["institutional_id"] is None

    @pytest.mark.asyncio
    @patch("app.core.policy.query_policy")
    async def test_check_module_permission_no_allow_key(self, mock_query_policy):
        """Test check_module_permission when policy returns no 'allow' key."""
        user = MagicMock()
        user.id = "user-123"
        user.email = "test@example.com"
        user.roles = [
            Role(role=RoleName.CO2_USER_PRINCIPAL, on=UnitScope(institutional_id="123"))
        ]

        # Policy returns dict without 'allow' key
        mock_query_policy.return_value = {"reason": "Unknown"}

        # Should raise exception (defaults to False when 'allow' is missing)
        with pytest.raises(HTTPException):
            await check_module_permission(user, "professional-travel", "view")


class TestQueryPolicyPermissionCheck:
    """Tests for query_policy with permission check policy."""

    @pytest.mark.asyncio
    async def test_query_policy_permission_check_with_user_object(self):
        """Test permission check policy with user dict and roles."""
        input_data = {
            "user": {
                "id": "user-123",
                "email": "test@example.com",
                "roles": [
                    {
                        "role": RoleName.CO2_USER_PRINCIPAL.value,
                        "on": {"kind": "unit", "institutional_id": "123"},
                    }
                ],
            },
            "path": "modules.professional_travel/123",
            "action": "view",
        }

        result = await query_policy("authz/permission/check", input_data)

        assert result["allow"] is True
        assert "Permission granted" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_permission_check_denied(self):
        """Test permission check policy when permission denied."""
        input_data = {
            "user": {
                "id": "user-456",
                "email": "test@example.com",
                "roles": [],
            },
            "path": "modules.professional_travel",
            "action": "edit",
        }

        result = await query_policy("authz/permission/check", input_data)

        assert result["allow"] is False
        assert "Permission denied" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_permission_check_missing_user(self):
        """Test permission check policy with missing user."""
        input_data = {
            "path": "modules.professional_travel",
            "action": "view",
        }

        result = await query_policy("authz/permission/check", input_data)

        assert result["allow"] is False
        assert "Missing user" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_permission_check_missing_path(self):
        """Test permission check policy with missing path."""
        input_data = {
            "user": {
                "id": "user-123",
                "email": "test@example.com",
                "roles": [],
            },
            "action": "view",
        }

        result = await query_policy("authz/permission/check", input_data)

        assert result["allow"] is False
        assert "missing" in result["reason"].lower()


class TestQueryPolicyDataFilter:
    """Tests for query_policy with data filter policies."""

    @pytest.mark.asyncio
    async def test_query_policy_data_list_global_scope(self):
        """Test data list policy for user with global scope."""
        input_data = {
            "user": {
                "id": 1,
                "email": "admin@example.com",
                "roles": [
                    {"role": RoleName.CO2_SUPERADMIN.value, "on": {"kind": "global"}}
                ],
            },
            "resource_type": "headcount",
            "action": "list",
        }

        result = await query_policy("authz/data/list", input_data)

        assert result["allow"] is True
        assert result["filters"]["scope"] == "global"
        assert "unit_ids" not in result["filters"]

    @pytest.mark.asyncio
    async def test_query_policy_data_list_unit_scope(self):
        """Test data list policy for user with unit scope."""
        input_data = {
            "user": {
                "id": 2,
                "email": "principal@example.com",
                "roles": [
                    {
                        "role": RoleName.CO2_USER_PRINCIPAL.value,
                        "on": {"kind": "unit", "institutional_id": "123"},
                    }
                ],
            },
            "resource_type": "equipment",
            "action": "list",
        }

        result = await query_policy("authz/data/list", input_data)

        assert result["allow"] is True
        assert result["filters"]["scope"] == "unit"
        assert "123" in result["filters"]["unit_ids"]

    @pytest.mark.asyncio
    async def test_query_policy_data_list_own_scope(self):
        """Test data list policy for standard user (own scope)."""
        input_data = {
            "user": {
                "id": 3,
                "email": "standard@example.com",
                "roles": [],
            },
            "resource_type": "professional_travel",
            "action": "list",
        }

        result = await query_policy("authz/data/list", input_data)

        assert result["allow"] is True
        assert result["filters"]["scope"] == "own"
        assert result["filters"]["user_id"] == 3

    @pytest.mark.asyncio
    async def test_query_policy_data_list_missing_user(self):
        """Test data list policy with missing user."""
        input_data = {
            "resource_type": "headcount",
            "action": "list",
        }

        result = await query_policy("authz/data/list", input_data)

        assert result["allow"] is False
        assert "Missing user" in result["reason"]


class TestQueryPolicyResourceAccess:
    """Tests for query_policy with resource access policy."""

    @pytest.mark.asyncio
    async def test_query_policy_resource_access_api_provider_denied(self):
        """Test resource access denies edit for API trips."""
        input_data = {
            "user": {
                "id": 1,
                "email": "user@example.com",
                "roles": [
                    {
                        "role": RoleName.CO2_USER_PRINCIPAL.value,
                        "on": {"kind": "unit", "institutional_id": "123"},
                    }
                ],
            },
            "resource_type": "professional_travel",
            "resource": {
                "id": 100,
                "provider": "api",
                "unit_id": "123",
            },
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is False
        assert "read-only" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_resource_access_global_scope_allow(self):
        """Test resource access allows for global scope admin."""
        input_data = {
            "user": {
                "id": 1,
                "email": "admin@example.com",
                "roles": [
                    {"role": RoleName.CO2_SUPERADMIN.value, "on": {"kind": "global"}}
                ],
            },
            "resource_type": "professional_travel",
            "resource": {
                "id": 100,
                "provider": "manual",
                "created_by": 999,
                "unit_id": "456",
            },
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is True
        assert "Global scope" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_resource_access_owner_allow(self):
        """Test resource access allows user to edit their own resource."""
        input_data = {
            "user": {
                "id": 123,
                "email": "user@example.com",
                "roles": [],
            },
            "resource_type": "professional_travel",
            "resource": {
                "id": 100,
                "provider": "manual",
                "created_by": 123,
                "unit_id": "456",
            },
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is True
        assert "Owner access" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_resource_access_missing_resource(self):
        """Test resource access with missing resource."""
        input_data = {
            "user": {
                "id": 1,
                "email": "user@example.com",
                "roles": [],
            },
            "resource_type": "professional_travel",
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is False
        assert "Missing resource" in result["reason"]

    @pytest.mark.asyncio
    async def test_query_policy_unknown_resource_type(self):
        """Test resource access with unknown resource type."""
        input_data = {
            "user": {
                "id": 1,
                "email": "user@example.com",
                "roles": [],
            },
            "resource_type": "unknown_type",
            "resource": {"id": 1},
        }

        result = await query_policy("authz/resource/access", input_data)

        assert result["allow"] is False
        assert "No policy defined" in result["reason"]


class TestQueryPolicyLegacy:
    """Tests for query_policy with legacy/fallback policy paths."""

    @pytest.mark.asyncio
    async def test_query_policy_legacy_allow(self):
        """Test legacy policy path returns allow."""
        input_data = {"filters": {"unit_ids": ["123"]}}

        result = await query_policy("authz/unit/list", input_data)

        assert result["allow"] is True
        assert "filters" in result

    @pytest.mark.asyncio
    async def test_query_policy_legacy_no_filters(self):
        """Test legacy policy path with no filters."""
        input_data = {}

        result = await query_policy("authz/resource/list", input_data)

        assert result["allow"] is True
        assert result["filters"] == {}


class TestRequirePlanAccess:
    """Simulator Plan scoping: shared plans are editable by unit members,
    deletion stays creator-only.
    """

    @staticmethod
    def _user(user_id: int, *, is_global: bool = False):
        user = MagicMock()
        user.id = user_id
        role = MagicMock()
        role.on = GlobalScope() if is_global else MagicMock()
        user.roles = [role] if is_global else []
        return user

    @staticmethod
    def _plan(created_by: int, *, shared: bool = False):
        plan = MagicMock()
        plan.created_by = created_by
        plan.is_viewable_by_unit_members = shared
        return plan

    def test_creator_can_view_and_edit(self):
        user = self._user(1)
        plan = self._plan(created_by=1)
        require_plan_access(user, plan, "view")
        require_plan_access(user, plan, "edit")

    def test_unshared_plan_is_invisible_to_other_members(self):
        user = self._user(2)
        plan = self._plan(created_by=1, shared=False)
        with pytest.raises(HTTPException) as exc:
            require_plan_access(user, plan, "view")
        assert exc.value.status_code == 404

    def test_shared_plan_is_editable_but_not_deletable_by_other_members(self):
        user = self._user(2)
        plan = self._plan(created_by=1, shared=True)
        require_plan_access(user, plan, "view")
        require_plan_access(user, plan, "edit")
        with pytest.raises(HTTPException) as exc:
            require_plan_access(user, plan, "manage")
        assert exc.value.status_code == 403

    def test_global_scope_bypasses_plan_scoping(self):
        user = self._user(99, is_global=True)
        plan = self._plan(created_by=1, shared=False)
        require_plan_access(user, plan, "view")
        require_plan_access(user, plan, "edit")

    def test_plan_is_visible_to_matches_view_rule(self):
        assert plan_is_visible_to(self._user(1), self._plan(created_by=1))
        assert not plan_is_visible_to(self._user(2), self._plan(created_by=1))
        assert plan_is_visible_to(self._user(2), self._plan(created_by=1, shared=True))


class TestRequirePlanScopeForReport:
    """The report-level plan-scope enforcer used by every report-addressed write."""

    @staticmethod
    def _report(project_id):
        report = MagicMock()
        report.carbon_project_id = project_id
        return report

    @pytest.mark.asyncio
    async def test_noop_when_report_has_no_project(self):
        db = MagicMock()
        db.get = AsyncMock()
        await require_plan_scope_for_report(db, MagicMock(), self._report(None), "edit")
        db.get.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_noop_for_calculator_report(self):
        from app.models.carbon_report import CarbonReportType

        project = MagicMock()
        project.carbon_report_type = CarbonReportType.CALCULATOR
        db = MagicMock()
        db.get = AsyncMock(return_value=project)
        # Would raise if plan scoping ran; a Calculator report must pass through.
        await require_plan_scope_for_report(db, MagicMock(), self._report(5), "edit")

    @pytest.mark.asyncio
    async def test_enforces_plan_access_for_plan_report(self):
        from fastapi import HTTPException

        from app.models.carbon_report import CarbonReportType

        project = MagicMock()
        project.carbon_report_type = CarbonReportType.SIMULATOR_PLAN
        project.created_by = 1
        project.is_viewable_by_unit_members = True
        db = MagicMock()
        db.get = AsyncMock(return_value=project)
        non_creator = MagicMock()
        non_creator.id = 2
        non_creator.roles = []
        await require_plan_scope_for_report(db, non_creator, self._report(5), "edit")

        project.is_viewable_by_unit_members = False
        with pytest.raises(HTTPException) as exc:
            await require_plan_scope_for_report(
                db, non_creator, self._report(5), "edit"
            )
        assert exc.value.status_code == 404


class TestCheckModulePermissionForReport:
    """Explore reports and Grant Proposal plan reports drop the module gate
    to unit membership (#1988, #1983); effective plan-year and Calculator
    reports delegate to the strict per-module gate.
    """

    @staticmethod
    def _report(project_id=5, unit_id=1, is_grant=False):
        report = MagicMock()
        report.carbon_project_id = project_id
        report.unit_id = unit_id
        report.is_grant = is_grant
        return report

    @staticmethod
    def _db(project_type, unit):
        from app.models.carbon_project import CarbonProject

        project = MagicMock()
        project.carbon_report_type = project_type

        async def _get(model, key):
            if model is CarbonProject:
                return project
            return unit

        db = MagicMock()
        db.get = AsyncMock(side_effect=_get)
        return db

    @staticmethod
    def _std_user(iid):
        user = MagicMock()
        user.roles = [
            Role(role=RoleName.CO2_USER_STD, on=OwnScope(institutional_id=iid))
        ]
        return user

    @staticmethod
    def _unit(iid="0184"):
        unit = MagicMock()
        unit.institutional_id = iid
        return unit

    @pytest.mark.asyncio
    async def test_explore_report_passes_for_std_unit_member(self):
        from app.models.carbon_report import CarbonReportType

        unit = self._unit("0184")
        result = await check_module_permission_for_report(
            current_user=self._std_user("0184"),
            module_id="headcount",
            action="view",
            db=self._db(CarbonReportType.SIMULATOR_EXPLORE, unit),
            report=self._report(),
        )
        assert result is unit

    @pytest.mark.asyncio
    async def test_plan_report_delegates_to_unit_gate(self):
        from app.models.carbon_report import CarbonReportType

        unit = self._unit("0184")
        user = self._std_user("0184")
        db = self._db(CarbonReportType.SIMULATOR_PLAN, unit)
        with patch(
            "app.core.policy.check_module_permission_for_unit",
            AsyncMock(return_value=unit),
        ) as delegate:
            result = await check_module_permission_for_report(
                current_user=user,
                module_id="equipment",
                action="edit",
                db=db,
                report=self._report(unit_id=7),
            )
        assert result is unit
        delegate.assert_awaited_once_with(
            current_user=user,
            module_id="equipment",
            action="edit",
            db=db,
            unit_id=7,
        )

    @pytest.mark.asyncio
    async def test_grant_plan_report_passes_for_std_unit_member(self):
        from app.models.carbon_report import CarbonReportType

        unit = self._unit("0184")
        result = await check_module_permission_for_report(
            current_user=self._std_user("0184"),
            module_id="equipment",
            action="edit",
            db=self._db(CarbonReportType.SIMULATOR_PLAN, unit),
            report=self._report(is_grant=True),
        )
        assert result is unit

    @pytest.mark.asyncio
    async def test_grant_plan_report_denies_std_of_other_unit(self):
        from app.models.carbon_report import CarbonReportType

        with pytest.raises(HTTPException) as exc:
            await check_module_permission_for_report(
                current_user=self._std_user("9999"),
                module_id="equipment",
                action="edit",
                db=self._db(CarbonReportType.SIMULATOR_PLAN, self._unit("0184")),
                report=self._report(is_grant=True),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_explore_report_denies_std_of_other_unit(self):
        from app.models.carbon_report import CarbonReportType

        with pytest.raises(HTTPException) as exc:
            await check_module_permission_for_report(
                current_user=self._std_user("9999"),
                module_id="headcount",
                action="view",
                db=self._db(CarbonReportType.SIMULATOR_EXPLORE, self._unit("0184")),
                report=self._report(),
            )
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_simulator_report_missing_unit_is_404(self):
        from app.models.carbon_report import CarbonReportType

        with pytest.raises(HTTPException) as exc:
            await check_module_permission_for_report(
                current_user=self._std_user("0184"),
                module_id="headcount",
                action="view",
                db=self._db(CarbonReportType.SIMULATOR_EXPLORE, None),
                report=self._report(),
            )
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_calculator_report_delegates_to_unit_gate(self):
        from app.models.carbon_report import CarbonReportType

        unit = self._unit("0184")
        user = self._std_user("0184")
        db = self._db(CarbonReportType.CALCULATOR, unit)
        with patch(
            "app.core.policy.check_module_permission_for_unit",
            AsyncMock(return_value=unit),
        ) as delegate:
            result = await check_module_permission_for_report(
                current_user=user,
                module_id="headcount",
                action="view",
                db=db,
                report=self._report(unit_id=7),
            )
        assert result is unit
        delegate.assert_awaited_once_with(
            current_user=user,
            module_id="headcount",
            action="view",
            db=db,
            unit_id=7,
        )

    @pytest.mark.asyncio
    async def test_report_without_project_delegates_to_unit_gate(self):
        unit = self._unit("0184")
        user = self._std_user("0184")
        db = MagicMock()
        db.get = AsyncMock()
        with patch(
            "app.core.policy.check_module_permission_for_unit",
            AsyncMock(return_value=unit),
        ) as delegate:
            result = await check_module_permission_for_report(
                current_user=user,
                module_id="headcount",
                action="view",
                db=db,
                report=self._report(project_id=None, unit_id=7),
            )
        assert result is unit
        db.get.assert_not_awaited()
        delegate.assert_awaited_once()
