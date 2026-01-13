"""Database models."""

from sqlmodel import Relationship

from .audit import DocumentVersion, DocumentVersionBase

# v2 models
from .carbon_report import (
    CarbonReport,
    CarbonReportBase,
    CarbonReportModule,
    CarbonReportModuleBase,
)
from .data_entry import DataEntry, DataEntryBase
from .data_entry_emission import DataEntryEmission, DataEntryEmissionBase
from .data_entry_type import DataEntryType, DataEntryTypeBase
from .emission_type import EmissionType, EmissionTypeBase
from .factor import Factor, FactorBase
from .module_type import ModuleType, ModuleTypeBase
from .unit import Unit, UnitBase
from .unit_user import UnitUser
from .user import User, UserBase

# IMPORTANT: Call model_rebuild() BEFORE adding relationships
User.model_rebuild()

# Unit <-> UnitUser relationships
Unit.unit_users = Relationship(back_populates="unit")
UnitUser.unit = Relationship(back_populates="unit_users")

User.unit_users = Relationship(back_populates="user")
UnitUser.user = Relationship(back_populates="unit_users")

# Unit -> User (principal_user) relationship
Unit.principal_user = Relationship(
    sa_relationship_kwargs={"foreign_keys": "[Unit.principal_user_provider_code]"}
)

# Unit <-> CarbonReport relationships
Unit.carbon_reports = Relationship(back_populates="unit")
CarbonReport.unit = Relationship(back_populates="carbon_reports")

# CarbonReport <-> CarbonReportModule relationships
CarbonReport.modules = Relationship(back_populates="carbon_report")
CarbonReportModule.carbon_report = Relationship(back_populates="modules")

# ModuleType <-> CarbonReportModule relationships
ModuleType.carbon_report_modules = Relationship(back_populates="module_type")
CarbonReportModule.module_type = Relationship(back_populates="carbon_report_modules")

# CarbonReportModule <-> DataEntry relationships
CarbonReportModule.data_entries = Relationship(back_populates="carbon_report_module")
DataEntry.carbon_report_module = Relationship(back_populates="data_entries")

# ModuleType <-> DataEntryType relationships
ModuleType.data_entry_types = Relationship(back_populates="module_type")
DataEntryType.module_type = Relationship(back_populates="data_entry_types")

# DataEntry <-> ModuleType/DataEntryType relationships (one-way)
DataEntry.module_type = Relationship()
DataEntry.data_entry_type = Relationship()

# DataEntry <-> DataEntryEmission relationships
DataEntry.emissions = Relationship(back_populates="data_entry")
DataEntryEmission.data_entry = Relationship(back_populates="emissions")

# EmissionType <-> DataEntryEmission relationships
EmissionType.data_entry_emissions = Relationship(back_populates="emission_type")
DataEntryEmission.emission_type = Relationship(back_populates="data_entry_emissions")

# EmissionType <-> Factor relationships
EmissionType.factors = Relationship(back_populates="emission_type")
Factor.emission_type = Relationship(back_populates="factors")

# DataEntryType <-> Factor relationships
DataEntryType.factors = Relationship(back_populates="data_entry_type")
Factor.data_entry_type = Relationship(back_populates="factors")

# Factor <-> DataEntryEmission relationships (primary_factor_id)
Factor.data_entry_emissions = Relationship(
    back_populates="primary_factor",
    sa_relationship_kwargs={"foreign_keys": "[DataEntryEmission.primary_factor_id]"},
)
DataEntryEmission.primary_factor = Relationship(
    back_populates="data_entry_emissions",
    sa_relationship_kwargs={"foreign_keys": "[DataEntryEmission.primary_factor_id]"},
)


__all__ = [
    # Unit
    "Unit",
    "UnitBase",
    "UnitUser",
    # User
    "User",
    "UserBase",
    # Emission types
    "EmissionType",
    "EmissionTypeBase",
    # Generic factors (unified model)
    "Factor",
    "FactorBase",
    # Carbon reports
    "CarbonReport",
    "CarbonReportBase",
    "CarbonReportModule",
    "CarbonReportModuleBase",
    # Data entries
    "DataEntry",
    "DataEntryBase",
    "DataEntryEmission",
    "DataEntryEmissionBase",
    "DataEntryType",
    "DataEntryTypeBase",
    # Module types
    "ModuleType",
    "ModuleTypeBase",
    # Audit
    "DocumentVersion",
    "DocumentVersionBase",
]
