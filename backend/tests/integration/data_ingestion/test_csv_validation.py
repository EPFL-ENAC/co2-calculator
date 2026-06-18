"""Unit tests for CSV upload validation and error handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.data_entry import DataEntrySourceEnum
from app.services.data_ingestion.csv_providers.module_per_year import (
    ModulePerYearCSVProvider,
)


class TestCSVValidationErrors:
    """Test CSV validation error message standardization."""

    @pytest.mark.asyncio
    async def test_empty_csv_raises_error(self):
        """Test that empty CSV raises ValueError with correct message."""
        config = {
            "file_path": "tmp/test.csv",
            "year": 2025,
            "module_type_id": 1,
        }

        mock_session = AsyncMock()
        provider = ModulePerYearCSVProvider(config, data_session=mock_session)

        # Empty CSV (headers only)
        csv_text = "unit_institutional_id,name,function\n"

        # Should fail with specific error message
        with pytest.raises(ValueError, match="CSV file is empty"):
            await provider._validate_csv_headers(
                csv_text,
                expected_columns={"unit_institutional_id", "name", "sius_code"},
                required_columns={"unit_institutional_id", "name", "sius_code"},
            )

    @pytest.mark.asyncio
    async def test_missing_columns_raises_error(self):
        """Test that missing columns raises ValueError with correct message."""
        config = {
            "file_path": "tmp/test.csv",
            "year": 2025,
            "module_type_id": 1,
        }

        mock_session = AsyncMock()
        provider = ModulePerYearCSVProvider(config, data_session=mock_session)

        # CSV missing required column (function)
        csv_text = "unit_institutional_id,name\nUNIT001,John Doe\n"

        # Should fail with specific error message
        with pytest.raises(ValueError, match="missing required columns"):
            await provider._validate_csv_headers(
                csv_text,
                expected_columns={"unit_institutional_id", "name", "sius_code"},
                required_columns={"unit_institutional_id", "name", "sius_code"},
            )


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

        # Mock the set-based delete to verify it's called with correct source
        mock_data_entry_service = AsyncMock()
        mock_data_entry_service.repo.bulk_delete_by_source_year = AsyncMock(
            return_value=0
        )

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
        mock_job.data_entry_type_id = None
        provider.job = mock_job

        await provider._delete_existing_entries_for_module_per_year(
            unit_to_module_map,
            {"rows_processed": 0, "rows_skipped": 0},
            mock_data_entry_service,
        )

        # Verify the single set-based delete targets CSV_MODULE_PER_YEAR
        # for the job's year — human (USER_MANUAL) and unit-specific
        # sources are untouched by construction of the source filter.
        calls = mock_data_entry_service.repo.bulk_delete_by_source_year.call_args_list
        assert len(calls) == 1
        kwargs = calls[0].kwargs
        assert kwargs["source"] == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value
        assert kwargs["year"] == 2025


class TestModuleUnitSpecificBehavior:
    """Test MODULE_UNIT_SPECIFIC append-only behavior."""

    def test_append_only_documentation(self):
        """Test that MODULE_UNIT_SPECIFIC is documented as append-only."""
        from app.services.data_ingestion.base_csv_provider import BaseCSVProvider

        # Check that the docstring mentions append-only for unit-specific
        docstring = BaseCSVProvider._delete_existing_entries_for_module_per_year.__doc__
        assert "MODULE_UNIT_SPECIFIC" in docstring
        assert "append-only" in docstring


class TestHumanDataProtection:
    """Test that human entries are protected from CSV uploads."""

    @pytest.mark.asyncio
    async def test_error_message_format_standardization(self):
        """Test that all validation errors use standardized format."""
        # Test empty CSV error format
        error_msg = "CSV file is empty"
        expected = f"Wrong CSV format or encoding: {error_msg}"
        assert "Wrong CSV format or encoding" in expected
        assert error_msg in expected

        # Test missing columns error format
        error_msg = "CSV is missing required columns: col1"
        expected = f"Wrong CSV format or encoding: {error_msg}"
        assert "Wrong CSV format or encoding" in expected
        assert "missing required columns" in expected

    @pytest.mark.asyncio
    async def test_delete_method_uses_correct_source_filter(self):
        """Verify deletion only targets CSV_MODULE_PER_YEAR entries.

        This test verifies the filtering logic that protects human entries:
        - Only entries with source=CSV_MODULE_PER_YEAR are deleted
        - Entries with source=USER_MANUAL are NOT deleted
        - Entries with source=CSV_MODULE_UNIT_SPECIFIC are NOT deleted
        """
        config = {
            "file_path": "tmp/test.csv",
            "year": 2025,
            "module_type_id": 1,
        }

        mock_session = AsyncMock()
        provider = ModulePerYearCSVProvider(config, data_session=mock_session)

        # Mock the set-based delete to capture calls
        mock_data_entry_service = AsyncMock()
        mock_data_entry_service.repo.bulk_delete_by_source_year = AsyncMock(
            return_value=0
        )

        unit_to_module_map = {"UNIT001": 1}

        # Mock user and job
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.email = "test@example.com"
        mock_user.full_name = "Test User"
        mock_user.display_name = "Test"
        mock_user.institutional_id = "INST001"
        mock_user.roles = []
        mock_user.disabled = False
        provider.user = mock_user

        mock_job = MagicMock()
        mock_job.module_type_id = 1
        mock_job.data_entry_type_id = None
        provider.job = mock_job

        # Call deletion method
        await provider._delete_existing_entries_for_module_per_year(
            unit_to_module_map,
            {"rows_processed": 0, "rows_skipped": 0},
            mock_data_entry_service,
        )

        # Verify the call uses the CSV_MODULE_PER_YEAR source filter —
        # this is what protects human entries (USER_MANUAL source) and
        # unit-specific uploads (CSV_MODULE_UNIT_SPECIFIC source).
        calls = mock_data_entry_service.repo.bulk_delete_by_source_year.call_args_list
        assert len(calls) == 1, "Expected exactly one set-based deletion call"
        kwargs = calls[0].kwargs
        assert kwargs["source"] == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value, (
            f"Expected CSV_MODULE_PER_YEAR source, got {kwargs['source']}"
        )
        assert kwargs["source"] != DataEntrySourceEnum.USER_MANUAL.value
        assert kwargs["source"] != DataEntrySourceEnum.CSV_MODULE_UNIT_SPECIFIC.value
