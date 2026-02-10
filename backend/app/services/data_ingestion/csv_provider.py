from typing import Any, Dict, List

import pandas as pd

from app.services.data_ingestion.base_provider import DataIngestionProvider

# from app.crud.data_entries import bulk_insert_data_entries
# from app.crud.headcount_entries import bulk_insert_headcount
# from app.crud.emission_factors import bulk_insert_factors


class CSVDataEntriesProvider(DataIngestionProvider):
    @property
    def provider_name(self) -> str:
        return "csv_upload"

    @property
    def target_type(self) -> str:
        return "data_entries"

    async def validate_connection(self) -> bool:
        file_path = self.config.get("file_path")
        if not file_path:
            return False
        try:
            pd.read_csv(file_path, nrows=1)
            return True
        except Exception:
            return False

    async def fetch_data(self, filters: Dict[str, Any]) -> List[Dict[str, Any]]:
        return []
