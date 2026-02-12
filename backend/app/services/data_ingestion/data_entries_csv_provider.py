"""
Backward compatibility module for CSV data ingestion providers.

This module re-exports the new refactored providers to maintain compatibility
with code that imports from this location.

New structure:
- BaseCSVProvider: base_csv_provider.py (shared logic)
- ModuleUnitSpecificCSVProvider: csv_providers/module_unit_specific.py
- ModulePerYearCSVProvider: csv_providers/module_per_year.py
"""

from app.services.data_ingestion.csv_providers import (
    ModulePerYearCSVProvider,
    ModuleUnitSpecificCSVProvider,
)

__all__ = [
    "ModuleUnitSpecificCSVProvider",
    "ModulePerYearCSVProvider",
]
