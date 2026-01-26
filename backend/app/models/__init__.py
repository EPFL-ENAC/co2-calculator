"""Database models."""

from sqlmodel import Relationship

from .carbon_report import CarbonReport, CarbonReportModule
from .data_entry import DataEntry
from .data_entry_emission import DataEntryEmission
from .data_entry_type import DataEntryType
from .data_ingestion import DataIngestionJob
from .emission_type import EmissionType
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
from .module_type import ModuleType
from .professional_travel import (
    ProfessionalTravel,
    ProfessionalTravelBase,
    ProfessionalTravelCreate,
    ProfessionalTravelEmission,
    ProfessionalTravelEmissionBase,
    ProfessionalTravelItemResponse,
    ProfessionalTravelList,
    ProfessionalTravelRead,
    ProfessionalTravelUpdate,
)
from .travel_impact_factor import (
    PlaneImpactFactor,
    PlaneImpactFactorBase,
    TrainImpactFactor,
    TrainImpactFactorBase,
)
from .unit import Unit
from .unit_user import UnitUser
from .user import User, UserBase

# IMPORTANT: Call model_rebuild() BEFORE adding relationships

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

# ModuleType <-> VariantType relationships
ModuleType.variant_types = Relationship(back_populates="module_type")
DataEntryType.module_type = Relationship(back_populates="variant_types")

# Module <-> ModuleType/VariantType relationships
DataEntry.module_type = Relationship()
DataEntry.data_entry_type = Relationship()

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
    "EmissionType",
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
    "DataEntryType",
    "DataEntryEmission",
    "PlaneImpactFactor",
    "PlaneImpactFactorBase",
    "TrainImpactFactor",
    "TrainImpactFactorBase",
]
