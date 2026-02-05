"""Database models."""

from sqlmodel import Relationship

from .carbon_report import CarbonReport, CarbonReportModule
from .data_entry import DataEntry
from .data_entry_emission import DataEntryEmission
from .data_ingestion import DataIngestionJob
from .factor import Factor
from .headcount import (
    HeadCount,
    HeadCountBase,
    HeadCountCreate,
    HeadCountRead,
    HeadCountUpdate,
)
from .location import (
    Location,
    LocationBase,
    LocationRead,
)
from .unit import Unit
from .unit_user import UnitUser
from .user import User, UserBase

# IMPORTANT: Call model_rebuild() BEFORE adding relationships
Unit.model_rebuild()
User.model_rebuild()
UnitUser.model_rebuild()
CarbonReport.model_rebuild()
CarbonReportModule.model_rebuild()
DataEntry.model_rebuild()
DataEntryEmission.model_rebuild()

# After model_rebuild()
Unit.unit_users = Relationship(back_populates="unit")
UnitUser.unit = Relationship(back_populates="unit_users")

User.unit_users = Relationship(back_populates="user")
UnitUser.user = Relationship(back_populates="unit_users")

# CarbonReport <-> CarbonReportModule relationships
CarbonReport.modules = Relationship(back_populates="carbon_report")
CarbonReportModule.carbon_report = Relationship(back_populates="modules")

# CarbonReportModule <-> Module relationships
CarbonReportModule.module_rows = Relationship(back_populates="carbon_report_module")
DataEntry.carbon_report_module = Relationship(back_populates="module_rows")

## implement join later then for equipment power_Factors
# and equipment_emissions and user if needed

DataEntryEmission.data_entry = Relationship()

__all__ = [
    "Unit",
    "User",
    "UserBase",
    "UnitUser",
    "DataIngestionJob",
    "Resource",
    "Factor",
    "HeadCount",
    "HeadCountBase",
    "HeadCountCreate",
    "HeadCountRead",
    "HeadCountUpdate",
    "CarbonReport",
    "CarbonReportModule",
    "Location",
    "LocationBase",
    "LocationRead",
    "ProfessionalTravel",
    "ProfessionalTravelBase",
    "ProfessionalTravelCreate",
    "ProfessionalTravelEmission",
    "ProfessionalTravelEmissionBase",
    "ProfessionalTravelItemResponse",
    "ProfessionalTravelList",
    "ProfessionalTravelRead",
    "ProfessionalTravelUpdate",
    "DataEntry",
    "DataEntryEmission",
    "PlaneImpactFactor",
    "PlaneImpactFactorBase",
    "TrainImpactFactor",
    "TrainImpactFactorBase",
]
