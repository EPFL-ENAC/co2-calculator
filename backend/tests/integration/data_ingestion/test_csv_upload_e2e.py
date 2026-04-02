"""Integration tests for CSV upload feature."""

import datetime
import os
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.main import app
from app.models.carbon_report import CarbonReport, CarbonReportModule
from app.models.data_entry import DataEntry, DataEntrySourceEnum, DataEntryTypeEnum
from app.models.data_ingestion import DataIngestionJob, IngestionState
from app.models.module_type import ModuleTypeEnum
from app.models.user import User, RoleEnum
from app.models.unit import Unit

# Test fixtures directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession):
    """Create a test user with necessary permissions."""
    user = User(
        email="test@example.com",
        full_name="Test User",
        roles=[RoleEnum.BACKOFFICE_METIER],
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_units(db_session: AsyncSession):
    """Create test units."""
    units = [
        Unit(institutional_id="UNIT001", name="Unit 1", accred_id="1"),
        Unit(institutional_id="UNIT002", name="Unit 2", accred_id="2"),
        Unit(institutional_id="UNIT003", name="Unit 3", accred_id="3"),
    ]
    db_session.add_all(units)
    await db_session.commit()
    return {u.institutional_id: u for u in units}


@pytest_asyncio.fixture
async def test_carbon_report_modules(db_session: AsyncSession, test_units):
    """Create test carbon reports and modules."""
    reports_and_modules = {}

    for unit in test_units.values():
        # Create carbon report
        report = CarbonReport(unit_id=unit.id, year=2025)
        db_session.add(report)
        await db_session.flush()

        # Create 7 modules for each report (as per system design)
        for module_type_id in range(1, 8):
            module = CarbonReportModule(
                carbon_report_id=report.id,
                module_type_id=module_type_id,
            )
            db_session.add(module)
            reports_and_modules[(unit.institutional_id, module_type_id)] = module

        await db_session.flush()

    await db_session.commit()
    return reports_and_modules


@pytest_asyncio.fixture
async def test_human_entries(db_session: AsyncSession, test_carbon_report_modules):
    """Create human-flagged data entries for testing protection."""
    entries = []

    # Create human entries for UNIT001, module_type 1
    module = test_carbon_report_modules.get(("UNIT001", 1))
    if module:
        for i in range(3):
            entry = DataEntry(
                data_entry_type_id=DataEntryTypeEnum.member,
                carbon_report_module_id=module.id,
                data={
                    "scientific": f"human_sci_{i}",
                    "member_uid": f"HUMAN_UID_{i}",
                    "member_name": f"Human User {i}",
                },
                source=DataEntrySourceEnum.USER_MANUAL.value,  # Human source
            )
            db_session.add(entry)
            entries.append(entry)

        await db_session.commit()

    return entries


@pytest.fixture
def get_test_client(test_user):
    """Create test client with authentication."""

    def _get_client():
        # In a real test, you'd need to set up proper auth headers
        # For now, we'll skip auth in tests or use a mock
        return TestClient(app)

    return _get_client


class TestCSVUploadIntegration:
    """Integration tests for CSV upload feature."""

    @pytest.mark.asyncio
    async def test_module_per_year_insert_new_rows(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_units: dict,
        test_carbon_report_modules: dict,
        get_test_client,
    ):
        """Test 1: Happy path - MODULE_PER_YEAR inserts new rows."""
        client = get_test_client()

        # Read valid CSV fixture
        csv_path = FIXTURES_DIR / "valid_module_per_year.csv"
        with open(csv_path, "rb") as f:
            files = {"files": ("valid_module_per_year.csv", f, "text/csv")}

            # Upload to temp storage first
            response = client.post(
                "/api/v1/files/temp-upload",
                files=files,
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            assert response.status_code == 200
            file_info = response.json()[0]
            file_path = file_info["path"]

        # Trigger CSV ingestion
        ingestion_request = {
            "ingestion_method": "csv",
            "target_type": 0,  # DATA_ENTRIES
            "year": 2025,
            "file_path": file_path,
        }

        response = client.post(
            f"/api/v1/data-entries/{ModuleTypeEnum.headcount.value}",
            json=ingestion_request,
            headers={"Authorization": f"Bearer {test_user.email}"},
        )
        assert response.status_code == 200
        job_data = response.json()
        job_id = job_data["job_id"]

        # Wait for job to complete (polling)
        import time

        max_attempts = 30
        for attempt in range(max_attempts):
            time.sleep(1)
            response = client.get(
                f"/api/v1/data-sync/jobs/{job_id}",
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            job_status = response.json()
            if job_status["state"] == IngestionState.FINISHED.value:
                break

        assert job_status["state"] == IngestionState.FINISHED.value
        assert "Success" in job_status["status_message"]

        # Verify rows were inserted
        result = await db_session.exec(
            select(DataEntry).where(
                DataEntry.source == DataEntrySourceEnum.CSV_MODULE_PER_YEAR.value
            )
        )
        entries = result.all()
        assert len(entries) > 0

    @pytest.mark.asyncio
    async def test_module_unit_specific_append_rows(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_carbon_report_modules: dict,
        get_test_client,
    ):
        """Test 2: MODULE_UNIT_SPECIFIC appends rows (no replacement)."""
        client = get_test_client()

        # Upload CSV twice
        csv_path = FIXTURES_DIR / "valid_module_unit_specific.csv"

        # First upload
        with open(csv_path, "rb") as f:
            files = {"files": ("upload1.csv", f, "text/csv")}
            response = client.post(
                "/api/v1/files/temp-upload",
                files=files,
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            file_path1 = response.json()[0]["path"]

        module = test_carbon_report_modules.get(("UNIT001", 1))
        ingestion_request = {
            "ingestion_method": "csv",
            "target_type": 0,
            "carbon_report_module_id": module.id,
            "file_path": file_path1,
        }

        response = client.post(
            f"/api/v1/data-entries/{ModuleTypeEnum.headcount.value}",
            json=ingestion_request,
            headers={"Authorization": f"Bearer {test_user.email}"},
        )

        # Second upload (should append, not replace)
        with open(csv_path, "rb") as f:
            files = {"files": ("upload2.csv", f, "text/csv")}
            response = client.post(
                "/api/v1/files/temp-upload",
                files=files,
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            file_path2 = response.json()[0]["path"]

        ingestion_request["file_path"] = file_path2
        response = client.post(
            f"/api/v1/data-entries/{ModuleTypeEnum.headcount.value}",
            json=ingestion_request,
            headers={"Authorization": f"Bearer {test_user.email}"},
        )

        # Verify entries were appended (doubled)
        result = await db_session.exec(
            select(DataEntry).where(
                DataEntry.carbon_report_module_id == module.id,
                DataEntry.source == DataEntrySourceEnum.CSV_MODULE_UNIT_SPECIFIC.value,
            )
        )
        entries = result.all()
        # Should have 2x the rows from the CSV
        assert len(entries) == 4  # 2 rows per upload

    @pytest.mark.asyncio
    async def test_human_entries_preserved_on_csv_upload(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_units: dict,
        test_carbon_report_modules: dict,
        test_human_entries: list,
        get_test_client,
    ):
        """Test 4: Human entries are preserved during CSV upload."""
        client = get_test_client()

        # Count human entries before upload
        result_before = await db_session.exec(
            select(DataEntry).where(
                DataEntry.source == DataEntrySourceEnum.USER_MANUAL.value
            )
        )
        human_entries_before = len(result_before.all())
        assert human_entries_before == 3

        # Upload CSV for same module
        csv_path = FIXTURES_DIR / "valid_module_per_year.csv"
        with open(csv_path, "rb") as f:
            files = {"files": ("test.csv", f, "text/csv")}
            response = client.post(
                "/api/v1/files/temp-upload",
                files=files,
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            file_path = response.json()[0]["path"]

        module = test_carbon_report_modules.get(("UNIT001", 1))
        ingestion_request = {
            "ingestion_method": "csv",
            "target_type": 0,
            "year": 2025,
            "file_path": file_path,
        }

        response = client.post(
            f"/api/v1/data-entries/{ModuleTypeEnum.headcount.value}",
            json=ingestion_request,
            headers={"Authorization": f"Bearer {test_user.email}"},
        )

        # Wait for completion
        import time

        job_id = response.json()["job_id"]
        for _ in range(30):
            time.sleep(1)
            response = client.get(
                f"/api/v1/data-sync/jobs/{job_id}",
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            if response.json()["state"] == IngestionState.FINISHED.value:
                break

        # Verify human entries still exist
        result_after = await db_session.exec(
            select(DataEntry).where(
                DataEntry.source == DataEntrySourceEnum.USER_MANUAL.value
            )
        )
        human_entries_after = len(result_after.all())
        assert human_entries_after == human_entries_before  # Still 3

    @pytest.mark.asyncio
    async def test_reject_non_csv_file(
        self,
        test_user: User,
        get_test_client,
    ):
        """Test 5: Reject non-CSV file with proper error message."""
        client = get_test_client()

        # Upload .txt file
        txt_path = FIXTURES_DIR / "not_a_csv.txt"
        with open(txt_path, "rb") as f:
            files = {"files": ("not_a_csv.txt", f, "text/plain")}
            response = client.post(
                "/api/v1/files/temp-upload",
                files=files,
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            file_path = response.json()[0]["path"]

        # Try to ingest
        ingestion_request = {
            "ingestion_method": "csv",
            "target_type": 0,
            "year": 2025,
            "file_path": file_path,
        }

        response = client.post(
            f"/api/v1/data-entries/{ModuleTypeEnum.headcount.value}",
            json=ingestion_request,
            headers={"Authorization": f"Bearer {test_user.email}"},
        )

        # Should fail during processing (not at upload)
        # Wait for job to fail
        import time

        job_id = response.json()["job_id"]
        for _ in range(30):
            time.sleep(1)
            response = client.get(
                f"/api/v1/data-sync/jobs/{job_id}",
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            job_status = response.json()
            if job_status["state"] == IngestionState.FINISHED.value:
                break

        assert job_status["state"] == IngestionState.FINISHED.value
        assert job_status["result"] == "error"
        assert "Wrong CSV format or encoding" in job_status["status_message"]

    @pytest.mark.asyncio
    async def test_reject_missing_required_columns(
        self,
        test_user: User,
        test_units: dict,
        get_test_client,
    ):
        """Test 7: Reject CSV with missing required columns."""
        client = get_test_client()

        # Upload CSV with missing columns
        csv_path = FIXTURES_DIR / "missing_required_columns.csv"
        with open(csv_path, "rb") as f:
            files = {"files": ("missing.csv", f, "text/csv")}
            response = client.post(
                "/api/v1/files/temp-upload",
                files=files,
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            file_path = response.json()[0]["path"]

        ingestion_request = {
            "ingestion_method": "csv",
            "target_type": 0,
            "year": 2025,
            "file_path": file_path,
        }

        response = client.post(
            f"/api/v1/data-entries/{ModuleTypeEnum.headcount.value}",
            json=ingestion_request,
            headers={"Authorization": f"Bearer {test_user.email}"},
        )

        # Wait for job to fail
        import time

        job_id = response.json()["job_id"]
        for _ in range(30):
            time.sleep(1)
            response = client.get(
                f"/api/v1/data-sync/jobs/{job_id}",
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            if response.json()["state"] == IngestionState.FINISHED.value:
                break

        job_status = response.json()
        assert job_status["result"] == "error"
        assert "Wrong CSV format or encoding" in job_status["status_message"]

    @pytest.mark.asyncio
    async def test_extra_columns_ignored(
        self,
        db_session: AsyncSession,
        test_user: User,
        test_units: dict,
        test_carbon_report_modules: dict,
        get_test_client,
    ):
        """Test 8: CSV with extra columns succeeds, extra columns ignored."""
        client = get_test_client()

        # Upload CSV with extra columns
        csv_path = FIXTURES_DIR / "with_extra_columns.csv"
        with open(csv_path, "rb") as f:
            files = {"files": ("extra.csv", f, "text/csv")}
            response = client.post(
                "/api/v1/files/temp-upload",
                files=files,
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            file_path = response.json()[0]["path"]

        ingestion_request = {
            "ingestion_method": "csv",
            "target_type": 0,
            "year": 2025,
            "file_path": file_path,
        }

        response = client.post(
            f"/api/v1/data-entries/{ModuleTypeEnum.headcount.value}",
            json=ingestion_request,
            headers={"Authorization": f"Bearer {test_user.email}"},
        )

        # Wait for completion
        import time

        job_id = response.json()["job_id"]
        for _ in range(30):
            time.sleep(1)
            response = client.get(
                f"/api/v1/data-sync/jobs/{job_id}",
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            if response.json()["state"] == IngestionState.FINISHED.value:
                break

        job_status = response.json()
        assert job_status["state"] == IngestionState.FINISHED.value
        assert job_status["result"] in ["success", "warning"]

    @pytest.mark.asyncio
    async def test_empty_csv_error(
        self,
        test_user: User,
        test_units: dict,
        get_test_client,
    ):
        """Test 9: Empty CSV (headers only) returns error."""
        client = get_test_client()

        # Upload empty CSV
        csv_path = FIXTURES_DIR / "empty.csv"
        with open(csv_path, "rb") as f:
            files = {"files": ("empty.csv", f, "text/csv")}
            response = client.post(
                "/api/v1/files/temp-upload",
                files=files,
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            file_path = response.json()[0]["path"]

        ingestion_request = {
            "ingestion_method": "csv",
            "target_type": 0,
            "year": 2025,
            "file_path": file_path,
        }

        response = client.post(
            f"/api/v1/data-entries/{ModuleTypeEnum.headcount.value}",
            json=ingestion_request,
            headers={"Authorization": f"Bearer {test_user.email}"},
        )

        # Wait for job to fail
        import time

        job_id = response.json()["job_id"]
        for _ in range(30):
            time.sleep(1)
            response = client.get(
                f"/api/v1/data-sync/jobs/{job_id}",
                headers={"Authorization": f"Bearer {test_user.email}"},
            )
            if response.json()["state"] == IngestionState.FINISHED.value:
                break

        job_status = response.json()
        assert job_status["result"] == "error"
        assert "Wrong CSV format or encoding" in job_status["status_message"]
        assert "CSV file is empty" in job_status["status_message"]
