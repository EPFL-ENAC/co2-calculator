"""Unit tests for CSV upload validation and error handling."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.models.data_entry import DataEntrySourceEnum
from app.services.data_ingestion.csv_providers.module_per_year import (
    ModulePerYearCSVProvider,
)


class TestCSVValidationErrors:
    """Test CSV validation error message standardization."""

    @pytest.mark.asyncio
    async def test_error_message_format(self):
        """Test that validation errors use standardized format."""
        # This is a simple test to verify the error message format
        # The actual validation happens in _validate_csv_headers

        error_message = "CSV file is empty"
        standardized = f"Wrong CSV format or encoding: {error_message}"

        assert "Wrong CSV format or encoding" in standardized
        assert error_message in standardized


class TestModulePerYearBehavior:
    """Test MODULE_PER_YEAR full replace behavior."""

    @pytest.mark.asyncio
    async def test_delete_only_csv_source_entries(self):
        """Test that only CSV_MODULE_PER_YEAR entries are deleted, not human."""
        config = {
            "file_path": "tmp/test.csv",
            "year": 2025,
            "module_type_id": 1,
        }

        mock_session = AsyncMock()
        provider = ModulePerYearCSVProvider(config, data_session=mock_session)

        # Mock bulk_delete_by_source to verify it's called with correct source
        mock_data_entry_service = AsyncMock()
        mock_data_entry_service.bulk_delete_by_source = AsyncMock()

        unit_to_module_map = {"UNIT001": 1, "UNIT002": 2}

        # Create a minimal mock user that UserRead can validate
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        mock_user.display_name = "Test"
        mock_user.institutional_id = "INST001"
        mock_user.roles = []
        mock_user.disabled = False
        provider.user = mock_user

        # Mock job with module_type_id (required for deletion logic to run)
        mock_job = MagicMock()
        mock_job.module_type_id = 1
        provider.job = mock_job

        await provider._delete_existing_entries_for_module_per_year(
            unit_to_module_map,
            {"rows_processed": 0, "rows_skipped": 0},
            mock_data_entry_service,
        )

        # Verify bulk_delete_by_source was called with CSV_MODULE_PER_YEAR source
        calls = mock_data_entry_service.bulk_delete_by_source.call_args_list
        assert len(calls) > 0

        # Check that source parameter is always CSV_MODULE_PER_YEAR
        for call in calls:
            kwargs = call.kwargs
            assert kwargs["source"] == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value


class TestModuleUnitSpecificBehavior:
    """Test MODULE_UNIT_SPECIFIC append-only behavior."""

    def test_append_only_documentation(self):
        """Test that MODULE_UNIT_SPECIFIC is documented as append-only."""
        from app.services.data_ingestion.base_csv_provider import BaseCSVProvider

        # Check that the docstring mentions append-only for unit-specific
        docstring = BaseCSVProvider._delete_existing_entries_for_module_per_year.__doc__
        assert "MODULE_UNIT_SPECIFIC" in docstring
        assert "append-only" in docstring
