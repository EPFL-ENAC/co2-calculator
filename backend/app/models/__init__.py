"""Database models."""

from sqlmodel import Relationship

from .carbon_report import CarbonReport, CarbonReportModule
from .data_ingestion import DataIngestionJob
from .emission_factor import (
    EmissionFactor,
    EmissionFactorBase,
    PowerFactor,
    PowerFactorBase,
)
from .equipment import (
    Equipment,
    EquipmentBase,
    EquipmentEmission,
    EquipmentEmissionBase,
)
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
from .module import Module, ModuleBase
from .module_type import ModuleType, ModuleTypeBase
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
from .variant_type import VariantType, VariantTypeBase

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
Module.carbon_report_module = Relationship(back_populates="module_rows")

# ModuleType <-> VariantType relationships
ModuleType.variant_types = Relationship(back_populates="module_type")
VariantType.module_type = Relationship(back_populates="variant_types")

# Module <-> ModuleType/VariantType relationships
Module.module_type = Relationship()
Module.variant_type = Relationship()

## implement join later then for equipment power_Factors
# and equipment_emissions and user if needed

__all__ = [
    "Unit",
    "User",
    "UserBase",
    "UnitUser",
    "DataIngestionJob",
    "Resource",
    "ResourceBase",
    "EmissionFactor",
    "EmissionFactorBase",
    "PowerFactor",
    "PowerFactorBase",
    "Equipment",
    "EquipmentBase",
    "EquipmentEmission",
    "EquipmentEmissionBase",
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
    "Module",
    "ModuleBase",
    "ModuleType",
    "ModuleTypeBase",
    "PlaneImpactFactor",
    "PlaneImpactFactorBase",
    "TrainImpactFactor",
    "TrainImpactFactorBase",
    "VariantType",
    "VariantTypeBase",
]
