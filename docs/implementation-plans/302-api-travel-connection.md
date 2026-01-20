# 🎯 Complete Implementation Plan: API Travel Sync

## Architecture Overview

You need a **plugin-based data ingestion system** that can handle multiple data sources (CSV, Tableau API, future APIs) with a unified status tracking mechanism and background job processing.

## Detailed Implementation Plan

### 1. **Status Tracking Schema Design**

**Database Changes:**

- Add a new `data_ingestion_jobs` table to track sync operations:

  ```sql
  CREATE TABLE data_ingestion_jobs (
    id SERIAL PRIMARY KEY,
    inventory_id INT REFERENCES inventories(id),
    module_type_id INT REFERENCES module_types(id),
    provider_type VARCHAR(50), -- 'csv_upload', 'tableau_api', etc.
    status VARCHAR(20), -- 'pending', 'processing', 'completed', 'failed'
    status_code INT, -- HTTP-like: 200, 400, 500, etc.
    message TEXT,
    metadata JSONB, -- {rows_processed: 123, errors: [...], etc.}
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_by INT REFERENCES users(id)
  );
  ```

- Modify `modules` table to add tracking fields:
  ```sql
  ALTER TABLE modules ADD COLUMN last_sync_status JSONB;
  -- Structure: {
  --   'csv_upload': {'status_code': 200, 'message': '...', 'last_run': '...'},
  --   'tableau_api': {'status_code': 200, 'message': '...', 'last_run': '...'}
  -- }
  ```

### 2. **Abstract Provider System**

Create a plugin architecture for data providers:

```python
# app/services/data_ingestion/base_provider.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any
from datetime import datetime

class DataIngestionProvider(ABC):
    """Abstract base class for data ingestion providers"""

    def __init__(self, inventory_id: int, module_type_id: int, user_id: int):
        self.inventory_id = inventory_id
        self.module_type_id = module_type_id
        self.user_id = user_id
        self.job_id = None

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate connection to data source"""
        pass

    @abstractmethod
    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch raw data from source"""
        pass

    @abstractmethod
    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform raw data to match our schema"""
        pass

    async def ingest(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Main ingestion workflow with error handling"""
        try:
            # Create job record
            self.job_id = await self._create_job_record()
            await self._update_job_status('processing', 102, 'Fetching data...')

            # Fetch
            raw_data = await self.fetch_data(filters or {})
            await self._update_job_status('processing', 103, f'Fetched {len(raw_data)} records')

            # Transform
            transformed_data = await self.transform_data(raw_data)
            await self._update_job_status('processing', 104, 'Transforming data...')

            # Load using existing service
            result = await self._load_data(transformed_data)

            # Success
            await self._update_job_status('completed', 200, f'Successfully processed {result["count"]} records')
            return {'status_code': 200, 'message': 'Success', 'data': result}

        except Exception as e:
            await self._update_job_status('failed', 500, str(e))
            return {'status_code': 500, 'message': str(e), 'data': None}

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Use existing DataEntriesService to insert data"""
        from app.services.data_entries_service import DataEntriesService
        # Implementation depends on your existing service
        pass

    async def _create_job_record(self) -> int:
        """Create job tracking record in DB"""
        pass

    async def _update_job_status(self, status: str, code: int, message: str):
        """Update job status in DB"""
        pass
```

### 3. **Tableau API Provider Implementation**

```python
# app/services/data_ingestion/tableau_provider.py
from .base_provider import DataIngestionProvider
from typing import List, Dict, Any
import requests
from datetime import datetime

class TableauFlightsProvider(DataIngestionProvider):
    """Tableau API provider for flight data"""

    def __init__(self, inventory_id: int, module_type_id: int, user_id: int, year: int):
        super().__init__(inventory_id, module_type_id, user_id)
        self.year = year
        # Load config from env/settings
        from app.core.config import settings
        self.config = settings.TABLEAU_CONFIG

    async def validate_connection(self) -> bool:
        """Test Tableau API connection"""
        try:
            # Reuse your existing auth logic
            from vizsql.auth.jwt import generate_jwt
            jwt_token = generate_jwt()
            # Test connection
            return True
        except Exception:
            return False

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch flight data from Tableau API"""
        # Use your existing query_cli logic
        from vizsql.vds.query_cli import main as query_tableau

        # Filter by year: IN_Departure date starts with {year}
        # Modify payload to include year filter
        result = query_tableau()  # Adapt to async if needed
        return result.get('data', [])

    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform Tableau flight data to carbon_reports schema"""
        transformed = []

        for record in raw_data:
            # Map Tableau fields to your schema
            entry = {
                'inventory_id': self.inventory_id,
                'sciper': record.get('Sciper'),
                'centre_financier': record.get('Centre financier'),
                'departure_date': self._parse_date(record.get('IN_Departure date')),
                'origin': record.get('IN_Segment origin'),
                'destination': record.get('IN_Segment destination'),
                'origin_code': record.get('IN_Segment origin airport code'),
                'destination_code': record.get('IN_Segment destination airport code'),
                'travel_class': self._normalize_class(record.get('IN_Segment class')),
                'supplier': record.get('IN_Supplier'),
                'ticket_number': record.get('IN_Ticket number'),
                'transport_type': record.get('TRANSPORT_TYPE'),
                'round_trip': record.get('ROUND_TRIP') == 'YES',
                'distance_km': record.get('OUT_DISTANCE_CORRECTED'),
                'co2_kg': record.get('OUT_CO2_CORRECTED'),
                'created_by': self.user_id,
            }
            transformed.append(entry)

        return transformed

    def _parse_date(self, date_str: str) -> datetime:
        """Parse YYYYMMDD to datetime"""
        if not date_str or len(date_str) != 8:
            return None
        return datetime.strptime(date_str, '%Y%m%d')

    def _normalize_class(self, class_str: str) -> str:
        """Normalize travel class names"""
        mapping = {
            'AIR ECONOMY CLASS': 'economy',
            'AIR BUSINESS CLASS': 'business',
            'AIR FIRST CLASS': 'first',
        }
        return mapping.get(class_str, 'economy')
```

### 4. **CSV Provider (for consistency)**

```python
# app/services/data_ingestion/csv_provider.py
from .base_provider import DataIngestionProvider
import pandas as pd
from typing import List, Dict, Any

class CSVUploadProvider(DataIngestionProvider):
    """CSV upload provider"""

    def __init__(self, inventory_id: int, module_type_id: int, user_id: int, file_path: str):
        super().__init__(inventory_id, module_type_id, user_id)
        self.file_path = file_path

    async def validate_connection(self) -> bool:
        """Validate CSV file exists and is readable"""
        try:
            pd.read_csv(self.file_path, nrows=1)
            return True
        except Exception:
            return False

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Read CSV file"""
        df = pd.read_csv(self.file_path)
        return df.to_dict('records')

    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform CSV data (implement based on your CSV schema)"""
        # Your existing CSV transformation logic
        pass
```

### 5. **FastAPI Endpoints**

```python
# app/api/v1/endpoints/data_ingestion.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from app.services.data_ingestion.tableau_provider import TableauFlightsProvider
from app.services.data_ingestion.csv_provider import CSVUploadProvider
from pydantic import BaseModel

router = APIRouter()

class TableauSyncRequest(BaseModel):
    inventory_id: int
    year: int
    module_type_id: int = 2  # Travel module

class SyncStatusResponse(BaseModel):
    job_id: int
    status: str
    message: str

@router.post("/sync/tableau-flights", response_model=SyncStatusResponse)
async def sync_tableau_flights(
    request: TableauSyncRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Trigger Tableau API sync for flight data"""

    provider = TableauFlightsProvider(
        inventory_id=request.inventory_id,
        module_type_id=request.module_type_id,
        user_id=current_user.id,
        year=request.year
    )

    # Validate connection first
    if not await provider.validate_connection():
        raise HTTPException(status_code=503, detail="Cannot connect to Tableau API")

    # Run ingestion in background
    background_tasks.add_task(provider.ingest, filters={'year': request.year})

    return {
        'job_id': provider.job_id,
        'status': 'pending',
        'message': f'Tableau sync initiated for year {request.year}'
    }

@router.get("/sync/status/{job_id}")
async def get_sync_status(job_id: int):
    """Get status of a sync job"""
    # Query data_ingestion_jobs table
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        'job_id': job.id,
        'status': job.status,
        'status_code': job.status_code,
        'message': job.message,
        'metadata': job.metadata,
        'started_at': job.started_at,
        'completed_at': job.completed_at
    }

@router.get("/modules/{module_id}/sync-history")
async def get_module_sync_history(module_id: int):
    """Get all sync jobs for a module"""
    jobs = await get_jobs_by_module(module_id)
    return jobs
```

### 6. **Background Task Service**

```python
# app/services/background_tasks.py
from fastapi import BackgroundTasks
import asyncio

class DataIngestionTaskManager:
    """Manages background ingestion tasks"""

    @staticmethod
    async def run_ingestion(provider, filters: dict):
        """Execute ingestion with error handling and logging"""
        try:
            result = await provider.ingest(filters)
            # Update module last_sync_status
            await update_module_sync_status(
                provider.inventory_id,
                provider.module_type_id,
                provider.__class__.__name__,
                result
            )
            return result
        except Exception as e:
            # Log error
            logger.error(f"Ingestion failed: {e}")
            raise
```

### 7. **Frontend Integration (Backoffice)**

```javascript
// In your backoffice admin panel
async function syncTableauAPI(inventoryId, year) {
  const response = await fetch("/api/v1/data-ingestion/sync/tableau-flights", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ inventory_id: inventoryId, year: year }),
  });

  const { job_id } = await response.json();

  // Poll for status
  const pollStatus = setInterval(async () => {
    const status = await fetch(`/api/v1/data-ingestion/sync/status/${job_id}`);
    const data = await status.json();

    updateUIStatus(data);

    if (data.status === "completed" || data.status === "failed") {
      clearInterval(pollStatus);
    }
  }, 2000);
}
```

### 8. **Configuration Management**

```python
# app/core/config.py
class Settings(BaseSettings):
    # ... existing settings

    # Tableau API Config
    TABLEAU_CONFIG: dict = {
        'server_url': os.getenv('TABLEAU_SERVER_URL'),
        'site_content_url': os.getenv('TABLEAU_SITE_CONTENT_URL'),
        'datasource_luid': os.getenv('TABLEAU_DS_FLIGHTS_LUID'),
        'client_id': os.getenv('TABLEAU_CONNECTED_APP_CLIENT_ID'),
        'secret_id': os.getenv('TABLEAU_CONNECTED_APP_SECRET_ID'),
        'secret_value': os.getenv('TABLEAU_CONNECTED_APP_SECRET_VALUE'),
        'username': os.getenv('TABLEAU_USERNAME'),
    }
```

---

## ✅ Summary: Implementation Checklist

- [ ] **Create `data_ingestion_jobs` table** with status tracking (status, status_code, message, metadata)
- [ ] **Build abstract `DataIngestionProvider` class** with validate/fetch/transform/ingest methods
- [ ] **Implement `TableauFlightsProvider`** extending base class, reusing your existing Tableau query code
- [ ] **Create FastAPI endpoint `/sync/tableau-flights`** that triggers background task using BackgroundTasks
- [ ] **Add `/sync/status/{job_id}` endpoint** to poll job progress
- [ ] **Integrate with existing `DataEntriesService`** to insert transformed records into `carbon_reports`
- [ ] **Add frontend "Connect API" button** in backoffice that calls sync endpoint and polls status
- [ ] **Test end-to-end**: Click button → background job fetches/transforms/loads → status updates → UI shows completion
- [ ] **(Optional) Add error handling**: Failed jobs show error messages, allow retry functionality
- [ ] **(Optional) Create `CSVUploadProvider`** to unify CSV upload logic with same pattern

UPDATE OF PLAN:

# 🎯 Refined API Design: Generic Data Sync Routes

You're absolutely right! We need a **generic, scalable routing structure** that can handle different modules, data entry types, and providers without hardcoding specific use cases.

## Revised Architecture

### 1. **Generic Route Structure**

```python
# app/api/v1/endpoints/data_sync.py
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from typing import Optional, Literal
from pydantic import BaseModel
from enum import Enum

router = APIRouter(prefix="/sync", tags=["data-sync"])

# --- Enums for type safety ---
class ProviderType(str, Enum):
    CSV_UPLOAD = "csv_upload"
    TABLEAU_API = "tableau_api"
    MANUAL_ENTRY = "manual_entry"
    # Future: SAP_API, EXTERNAL_DB, etc.

class SyncRequest(BaseModel):
    provider_type: ProviderType
    year: int
    filters: Optional[dict] = {}  # Flexible filters for different providers
    config: Optional[dict] = {}   # Provider-specific config overrides

class SyncStatusResponse(BaseModel):
    job_id: int
    status: str
    status_code: int
    message: str
    progress: Optional[dict] = None

# --- Generic Routes ---

@router.post("/data-entries/{module_id}", response_model=SyncStatusResponse)
async def sync_module_data_entries(
    module_id: int,
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """
    Generic sync endpoint for ANY module's data entries.

    Examples:
    - POST /sync/data-entries/2 (Travel module)
    - POST /sync/data-entries/5 (Headcount module)

    Body: {
        "provider_type": "tableau_api",
        "year": 2025,
        "filters": {"centre_financier": "F0892"}
    }
    """

    # Get module info from DB to determine what kind of data entries it uses
    module = await get_module_by_id(module_id)
    if not module:
        raise HTTPException(status_code=404, detail="Module not found")

    # Get the appropriate provider based on module type + provider type
    provider = await ProviderFactory.create_provider(
        module=module,
        provider_type=request.provider_type,
        user_id=current_user.id,
        year=request.year,
        config=request.config
    )

    if not provider:
        raise HTTPException(
            status_code=400,
            detail=f"Provider '{request.provider_type}' not supported for module '{module.module_type.name}'"
        )

    # Validate connection
    if not await provider.validate_connection():
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to {request.provider_type}"
        )

    # Create job and run in background
    job_id = await provider.create_job()
    background_tasks.add_task(
        run_sync_task,
        provider=provider,
        filters=request.filters
    )

    return {
        'job_id': job_id,
        'status': 'pending',
        'status_code': 102,
        'message': f'Sync initiated for {module.module_type.name} using {request.provider_type}',
        'progress': None
    }


@router.post("/factors/{module_id}/{factor_type_id}", response_model=SyncStatusResponse)
async def sync_module_factors(
    module_id: int,
    factor_type_id: int,
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """
    Generic sync endpoint for emission factors within a module.

    Examples:
    - POST /sync/factors/2/3 (Travel module, flight emission factors)
    - POST /sync/factors/5/7 (Headcount module, heating factors)

    Body: {
        "provider_type": "csv_upload",
        "year": 2025,
        "config": {"file_path": "/uploads/factors_2025.csv"}
    }
    """

    module = await get_module_by_id(module_id)
    factor_type = await get_factor_type_by_id(factor_type_id)

    if not module or not factor_type:
        raise HTTPException(status_code=404, detail="Module or factor type not found")

    # Similar logic to data entries sync
    provider = await ProviderFactory.create_provider(
        module=module,
        provider_type=request.provider_type,
        user_id=current_user.id,
        year=request.year,
        config=request.config,
        target_type='factors',
        factor_type_id=factor_type_id
    )

    job_id = await provider.create_job()
    background_tasks.add_task(run_sync_task, provider=provider, filters=request.filters)

    return {
        'job_id': job_id,
        'status': 'pending',
        'status_code': 102,
        'message': f'Factor sync initiated for {factor_type.name}',
        'progress': None
    }


@router.get("/status/{job_id}", response_model=SyncStatusResponse)
async def get_sync_status(job_id: int):
    """Get real-time status of any sync job"""
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        'job_id': job.id,
        'status': job.status,
        'status_code': job.status_code,
        'message': job.message,
        'progress': job.metadata.get('progress') if job.metadata else None
    }


@router.get("/history/{module_id}")
async def get_module_sync_history(
    module_id: int,
    provider_type: Optional[ProviderType] = None,
    limit: int = Query(50, le=200)
):
    """
    Get sync history for a module, optionally filtered by provider type.

    Examples:
    - GET /sync/history/2
    - GET /sync/history/2?provider_type=tableau_api&limit=10
    """
    jobs = await get_jobs_by_module(
        module_id=module_id,
        provider_type=provider_type,
        limit=limit
    )
    return jobs


@router.post("/retry/{job_id}")
async def retry_failed_sync(
    job_id: int,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user)
):
    """Retry a failed sync job"""
    job = await get_job_by_id(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != 'failed':
        raise HTTPException(status_code=400, detail="Can only retry failed jobs")

    # Recreate provider from job metadata
    provider = await ProviderFactory.recreate_from_job(job)

    # Create new job (or reset existing one)
    new_job_id = await provider.create_job()
    background_tasks.add_task(run_sync_task, provider=provider, filters=job.metadata.get('filters', {}))

    return {'job_id': new_job_id, 'message': 'Retry initiated'}
```

---

### 2. **Provider Factory Pattern**

```python
# app/services/data_ingestion/provider_factory.py
from typing import Optional
from app.models.module import Module
from app.services.data_ingestion.base_provider import DataIngestionProvider
from app.services.data_ingestion.tableau_provider import TableauFlightsProvider
from app.services.data_ingestion.csv_provider import CSVDataEntriesProvider, CSVFactorsProvider

class ProviderFactory:
    """Factory to create the right provider based on module + provider type"""

    # Registry of available providers
    PROVIDERS = {
        # Data Entries providers
        ('travel', 'tableau_api', 'data_entries'): TableauFlightsProvider,
        ('travel', 'csv_upload', 'data_entries'): CSVDataEntriesProvider,
        ('headcount', 'csv_upload', 'data_entries'): CSVDataEntriesProvider,
        ('purchases', 'csv_upload', 'data_entries'): CSVDataEntriesProvider,

        # Factors providers
        ('travel', 'csv_upload', 'factors'): CSVFactorsProvider,
        ('headcount', 'csv_upload', 'factors'): CSVFactorsProvider,

        # Future: Add more as needed
        # ('travel', 'sap_api', 'data_entries'): SAPTravelProvider,
    }

    @classmethod
    async def create_provider(
        cls,
        module: Module,
        provider_type: str,
        user_id: int,
        year: int,
        config: dict = None,
        target_type: str = 'data_entries',  # 'data_entries' or 'factors'
        factor_type_id: Optional[int] = None
    ) -> Optional[DataIngestionProvider]:
        """
        Create the appropriate provider instance.

        Args:
            module: The module to sync data for
            provider_type: Type of provider (csv_upload, tableau_api, etc.)
            user_id: User initiating the sync
            year: Year to sync data for
            config: Provider-specific configuration
            target_type: What to sync - 'data_entries' or 'factors'
            factor_type_id: If syncing factors, which factor type
        """

        module_name = module.module_type.name.lower()
        key = (module_name, provider_type, target_type)

        provider_class = cls.PROVIDERS.get(key)
        if not provider_class:
            return None

        # Instantiate with appropriate parameters
        if target_type == 'data_entries':
            return provider_class(
                inventory_id=module.inventory_id,
                module_id=module.id,
                module_type_id=module.module_type_id,
                user_id=user_id,
                year=year,
                config=config or {}
            )
        else:  # factors
            return provider_class(
                inventory_id=module.inventory_id,
                module_id=module.id,
                module_type_id=module.module_type_id,
                factor_type_id=factor_type_id,
                user_id=user_id,
                year=year,
                config=config or {}
            )

    @classmethod
    async def recreate_from_job(cls, job):
        """Recreate a provider from a failed job for retry"""
        # Extract info from job.metadata
        module = await get_module_by_id(job.module_id)
        return await cls.create_provider(
            module=module,
            provider_type=job.provider_type,
            user_id=job.created_by,
            year=job.metadata.get('year'),
            config=job.metadata.get('config'),
            target_type=job.metadata.get('target_type', 'data_entries'),
            factor_type_id=job.metadata.get('factor_type_id')
        )
```

---

### 3. **Updated Base Provider**

```python
# app/services/data_ingestion/base_provider.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

class DataIngestionProvider(ABC):
    """Abstract base class for all data ingestion providers"""

    def __init__(
        self,
        inventory_id: int,
        module_id: int,
        module_type_id: int,
        user_id: int,
        year: int,
        config: Dict[str, Any] = None
    ):
        self.inventory_id = inventory_id
        self.module_id = module_id
        self.module_type_id = module_type_id
        self.user_id = user_id
        self.year = year
        self.config = config or {}
        self.job_id: Optional[int] = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier for this provider (e.g., 'tableau_api', 'csv_upload')"""
        pass

    @property
    @abstractmethod
    def target_type(self) -> str:
        """What this provider syncs: 'data_entries' or 'factors'"""
        pass

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Validate connection to data source"""
        pass

    @abstractmethod
    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Fetch raw data from source"""
        pass

    @abstractmethod
    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Transform raw data to match target schema"""
        pass

    async def create_job(self) -> int:
        """Create a job record in data_ingestion_jobs table"""
        from app.crud.data_ingestion import create_ingestion_job

        job = await create_ingestion_job(
            inventory_id=self.inventory_id,
            module_id=self.module_id,
            module_type_id=self.module_type_id,
            provider_type=self.provider_name,
            target_type=self.target_type,
            created_by=self.user_id,
            metadata={
                'year': self.year,
                'config': self.config,
                'filters': {}
            }
        )
        self.job_id = job.id
        return job.id

    async def ingest(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Main ingestion workflow"""
        try:
            await self._update_job('processing', 102, 'Starting sync...')

            # Fetch
            raw_data = await self.fetch_data(filters or {})
            await self._update_job('processing', 103, f'Fetched {len(raw_data)} records',
                                   {'progress': {'fetched': len(raw_data)}})

            # Transform
            transformed_data = await self.transform_data(raw_data)
            await self._update_job('processing', 104, 'Transforming data...',
                                   {'progress': {'transformed': len(transformed_data)}})

            # Load
            result = await self._load_data(transformed_data)

            # Success
            await self._update_job('completed', 200,
                                   f'Successfully processed {result["inserted"]} records',
                                   {'progress': {'completed': result["inserted"]}})

            return {'status_code': 200, 'message': 'Success', 'data': result}

        except Exception as e:
            await self._update_job('failed', 500, str(e), {'error': str(e)})
            raise

    @abstractmethod
    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Load transformed data into target table (data_entries or factors)"""
        pass

    async def _update_job(self, status: str, code: int, message: str, extra_metadata: dict = None):
        """Update job status"""
        from app.crud.data_ingestion import update_ingestion_job

        metadata = {'filters': {}, 'year': self.year}
        if extra_metadata:
            metadata.update(extra_metadata)

        await update_ingestion_job(
            job_id=self.job_id,
            status=status,
            status_code=code,
            message=message,
            metadata=metadata,
            completed_at=datetime.utcnow() if status in ['completed', 'failed'] else None
        )
```

---

### 4. **Concrete Providers**

```python
# app/services/data_ingestion/tableau_provider.py
from .base_provider import DataIngestionProvider
from typing import List, Dict, Any

class TableauFlightsProvider(DataIngestionProvider):
    """Tableau API provider for flight data entries"""

    @property
    def provider_name(self) -> str:
        return "tableau_api"

    @property
    def target_type(self) -> str:
        return "data_entries"

    async def validate_connection(self) -> bool:
        # Your existing connection validation
        pass

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Your existing Tableau query logic
        # Use self.year to filter by departure date
        pass

    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Transform Tableau records to carbon_reports schema
        pass

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert into carbon_reports (data_entries for travel)"""
        from app.crud.carbon_reports import bulk_insert_carbon_reports

        result = await bulk_insert_carbon_reports(data)
        return {'inserted': len(result)}


# app/services/data_ingestion/csv_provider.py
class CSVDataEntriesProvider(DataIngestionProvider):
    """Generic CSV provider for data entries (any module)"""

    @property
    def provider_name(self) -> str:
        return "csv_upload"

    @property
    def target_type(self) -> str:
        return "data_entries"

    async def validate_connection(self) -> bool:
        # Check if file exists at self.config['file_path']
        pass

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        # Read CSV from self.config['file_path']
        pass

    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # Module-specific transformation based on self.module_type_id
        pass

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        # Route to correct table based on module type
        if self.module_type_id == 2:  # Travel
            from app.crud.carbon_reports import bulk_insert_carbon_reports
            result = await bulk_insert_carbon_reports(data)
        elif self.module_type_id == 5:  # Headcount
            from app.crud.headcount_entries import bulk_insert_headcount
            result = await bulk_insert_headcount(data)
        # ... etc

        return {'inserted': len(result)}


class CSVFactorsProvider(DataIngestionProvider):
    """CSV provider for emission factors"""

    def __init__(self, *args, factor_type_id: int, **kwargs):
        super().__init__(*args, **kwargs)
        self.factor_type_id = factor_type_id

    @property
    def provider_name(self) -> str:
        return "csv_upload"

    @property
    def target_type(self) -> str:
        return "factors"

    async def _load_data(self, data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Insert into emission_factors table"""
        from app.crud.emission_factors import bulk_insert_factors

        result = await bulk_insert_factors(data, factor_type_id=self.factor_type_id)
        return {'inserted': len(result)}
```

---

### 5. **Database Schema Update**

```sql
-- Updated data_ingestion_jobs table
CREATE TABLE data_ingestion_jobs (
    id SERIAL PRIMARY KEY,
    inventory_id INT REFERENCES inventories(id),
    module_id INT REFERENCES modules(id),
    module_type_id INT REFERENCES module_types(id),
    provider_type VARCHAR(50) NOT NULL,  -- 'csv_upload', 'tableau_api', etc.
    target_type VARCHAR(20) NOT NULL,     -- 'data_entries', 'factors'
    status VARCHAR(20) NOT NULL,          -- 'pending', 'processing', 'completed', 'failed'
    status_code INT NOT NULL,             -- HTTP-like codes
    message TEXT,
    metadata JSONB,                       -- {year, filters, progress, errors, etc.}
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    created_by INT REFERENCES users(id),

    INDEX idx_module_provider (module_id, provider_type),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at DESC)
);

-- Update modules table to track last sync per provider
ALTER TABLE modules ADD COLUMN sync_status JSONB DEFAULT '{}';
-- Structure: {
--   'tableau_api': {'last_job_id': 123, 'status': 'completed', 'last_run': '2025-01-14T...'},
--   'csv_upload': {'last_job_id': 124, 'status': 'completed', 'last_run': '2025-01-10T...'}
-- }
```

---

## ✅ Updated Implementation Checklist (8 hours)

- [ ] **Create `data_ingestion_jobs` table** with `target_type` field (data_entries/factors)
- [ ] **Build `ProviderFactory`** with registry mapping (module, provider_type, target_type) → Provider class
- [ ] **Update `DataIngestionProvider` base class** with `provider_name`, `target_type` properties
- [ ] **Implement `TableauFlightsProvider`** for travel data entries (reuse existing Tableau code)
- [ ] **Create generic routes**: `/sync/data-entries/{module_id}` and `/sync/factors/{module_id}/{factor_type_id}`
- [ ] **Add `/sync/status/{job_id}` and `/sync/history/{module_id}`** endpoints
- [ ] **Frontend: Add "Sync API" button** that calls `/sync/data-entries/{module_id}` with provider dropdown
- [ ] **Test complete flow**: Click sync → job created → background task runs → status updates → data appears in DB

**Time estimates:**

- Database + models: 1h
- Base provider + factory: 1.5h
- Tableau provider implementation: 2h
- FastAPI endpoints: 1.5h
- Frontend integration: 1.5h
- Testing + debugging: 30min

Here is the comprehensive **Spec-Driven Development Plan** for the Generic Data Ingestion System.

This specification prioritizes **contracts first**: strictly defining the Database Schema, API Interface, and Class Hierarchy before implementation logic is written. This ensures the system is scalable (adding a new provider is just adding a new class) and consistent (all providers behave exactly the same way).

---

# 🎯 Engineering Spec: Generic Data Ingestion System

## 1. Architecture Overview

**Objective:** specific logic for fetching data (e.g., Tableau, CSV, API) must be decoupled from the generic logic of tracking job status, handling errors, and updating the database.

**Core Patterns:**

- **Strategy Pattern:** To swap between `TableauProvider`, `CSVProvider`, etc., while maintaining a consistent `.ingest()` interface.
- **Factory Pattern:** To dynamically instantiate the correct provider based on `module_id` and `provider_type`.
- **State Machine:** To rigidly define job states (`pending` → `processing` → `completed`).

## 2. Database Schema Specification

This is the "Source of Truth" for all sync operations.

### New Table: `data_ingestion_jobs`

Tracks every sync attempt, whether manual entry, CSV upload, or API pull.

```sql
CREATE TABLE data_ingestion_jobs (
    id SERIAL PRIMARY KEY,
    inventory_id INT NOT NULL REFERENCES inventories(id),
    module_id INT REFERENCES modules(id),            -- Nullable if syncing global factors
    factor_type_id INT REFERENCES factor_types(id),  -- Nullable if syncing data entries

    -- Configuration & Type
    provider_type VARCHAR(50) NOT NULL,              -- e.g., 'tableau_api', 'csv_upload'
    target_type VARCHAR(50) NOT NULL,                -- 'data_entries' or 'factors'
    year INT NOT NULL,

    -- Status Tracking
    status VARCHAR(20) NOT NULL DEFAULT 'pending',   -- 'pending', 'processing', 'completed', 'failed'
    status_code INT,                                 -- 102 (Processing), 200 (OK), 500 (Error)
    message TEXT,                                    -- User-friendly status message

    -- Audit & Debug
    metadata JSONB DEFAULT '{}',                     -- { "rows_fetched": 150, "errors": [], "config": {...} }
    created_by INT REFERENCES users(id),
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_jobs_module ON data_ingestion_jobs(module_id);
CREATE INDEX idx_jobs_status ON data_ingestion_jobs(status);

```

### Updates: `modules`

Optimization to allow the UI to show status without querying the jobs table history.

```sql
ALTER TABLE modules ADD COLUMN last_sync_status JSONB DEFAULT '{}';
-- Schema: { "last_run": "ISO8601", "status": "completed", "provider": "tableau_api" }

```

## 3. API Contract (OpenAPI/Swagger Spec)

These endpoints are generic. They do not mention "Travel" or "Flights" in the URL, allowing the frontend to use the same component for all modules.

### A. Sync Data Entries

- **Route:** `POST /api/v1/sync/data-entries/{module_id}`
- **Description:** Triggers a background sync for activity data (e.g., Flights, Commuting, Energy).

**Request Body (`SyncRequest`):**

```json
{
  "provider_type": "tableau_api",
  "year": 2025,
  "filters": { "center_id": "123" },
  "config": {}
}
```

**Response (`SyncStatusResponse`):**

```json
{
  "job_id": 405,
  "status": "pending",
  "status_code": 102,
  "message": "Tableau sync initiated..."
}
```

### B. Sync Emission Factors

- **Route:** `POST /api/v1/sync/factors/{module_id}/{factor_type_id}`
- **Description:** Triggers a background sync for emission factors.
- **Request:** Same as above, but usually `provider_type` is `csv_upload`.

### C. Poll Job Status

- **Route:** `GET /api/v1/sync/status/{job_id}`
- **Description:** Polling endpoint for the frontend progress bar.

---

## 4. Internal Component Specification (Python)

### A. The Provider Factory

The `ProviderFactory` is the traffic controller. It ensures we never instantiate an invalid combination (e.g., trying to use Tableau API for Employee Commuting if we haven't built that yet).

```python
# app/services/data_ingestion/provider_factory.py

class ProviderFactory:
    # Registry mapping (module_slug, provider_type, target) -> ProviderClass
    REGISTRY = {
        ('travel', 'tableau_api', 'data_entries'): TableauFlightsProvider,
        ('travel', 'csv_upload', 'data_entries'): CSVTravelProvider,
        ('headcount', 'csv_upload', 'data_entries'): CSVHeadcountProvider,
        ('generic', 'csv_upload', 'factors'): CSVFactorsProvider
    }

    @classmethod
    async def get_provider(cls, module, provider_type, target_type, **kwargs):
        # Logic to lookup class in REGISTRY and instantiate it
        # Returns instance of DataIngestionProvider

```

### B. The Abstract Base Class

This enforces the "Spec" part of Spec-Driven Development. All providers _must_ adhere to this lifecycle.

```python
# app/services/data_ingestion/base_provider.py

class DataIngestionProvider(ABC):

    @abstractmethod
    async def validate_connection(self) -> bool:
        """Ping the API or check if CSV file exists."""
        pass

    @abstractmethod
    async def fetch_data(self) -> List[Dict]:
        """Get raw data. Returns list of dicts."""
        pass

    @abstractmethod
    async def transform_data(self, raw_data: List[Dict]) -> List[Dict]:
        """Map raw column names to our DB schema column names."""
        pass

    @abstractmethod
    async def load_data(self, clean_data: List[Dict]) -> Dict:
        """Insert into final table (carbon_reports or emission_factors)."""
        pass

    async def run_pipeline(self):
        """
        The Template Method that executes the flow:
        1. Update Job -> 'Processing'
        2. validate_connection()
        3. fetch_data()
        4. transform_data()
        5. load_data()
        6. Update Job -> 'Completed'
        7. Catch Exceptions -> Update Job 'Failed'
        """

```

### C. The Concrete Implementation (Tableau Travel)

This is the only place where specific business logic lives.

```python
# app/services/data_ingestion/tableau_provider.py

class TableauFlightsProvider(DataIngestionProvider):

    async def fetch_data(self):
        # 1. Generate JWT
        # 2. Call Tableau API with self.year filter
        # 3. Return raw JSON
        pass

    async def transform_data(self, raw_data):
        # Map 'IN_Departure_Date' -> 'departure_date'
        # Map 'IN_Class' -> 'travel_class' (normalize 'Business' vs 'Eco')
        return [ ... ]

    async def load_data(self, clean_data):
        # Call CRUD service to bulk insert into `carbon_reports`
        pass

```

---

## 5. Workflow Implementation Steps

### Phase 1: Foundation (The Skeleton)

1. **Database Migration:** Create `data_ingestion_jobs` table.
2. **Base Class:** Implement `DataIngestionProvider` with the `run_pipeline` logic handling the status updates and error catching.
3. **API Shell:** Create the generic FastAPI endpoints (`/sync/data-entries/...`) that accept the payload but currently just return a "Not Implemented" error.

### Phase 2: The Factory & Logic (The Brains)

4. **Factory Logic:** Implement `ProviderFactory` and the registry system.
5. **Task Manager:** Set up the `BackgroundTasks` handler in FastAPI to ensure the generic `run_pipeline` method is called asynchronously.

### Phase 3: The Implementations (The Muscle)

6. **Tableau Provider:** Implement `TableauFlightsProvider`.

- _Unit Test:_ Mock the Tableau API response and verify `transform_data` outputs correct DB schema.

7. **CSV Provider:** Implement generic `CSVProvider` (reusable for different modules).

### Phase 4: Integration

8. **Frontend Hook:** Connect the Backoffice "Sync" button to the generic endpoint.
9. **Poller:** Implement the frontend poller to check `/sync/status/{job_id}`.

---

## ✅ Summary: Implementation Checklist

- [ ] **Database:** Create `data_ingestion_jobs` table with proper indexes and JSONB metadata.
- [ ] **Architecture:** Implement abstract `DataIngestionProvider` (the contract) with the standard lifecycle methods (`validate`, `fetch`, `transform`, `load`).
- [ ] **Logic:** Build `ProviderFactory` to dynamically route requests based on Module + Provider Type.
- [ ] **API:** Create generic endpoints `/sync/data-entries/{id}` and `/sync/factors/{id}`.
- [ ] **Provider:** Implement `TableauFlightsProvider` containing the specific mapping logic for Travel.
- [ ] **Provider:** Implement generic `CSVDataEntriesProvider` as a fallback/alternative.
- [ ] **Async:** Wire up FastAPI `BackgroundTasks` to execute the ingestion pipeline without blocking the UI.
- [ ] **UI/UX:** Add status polling endpoint `/sync/status/{job_id}` and connect to Frontend progress bar.
- [ ] **Integration:** Verify that a successful sync updates the `modules.last_sync_status` field.
