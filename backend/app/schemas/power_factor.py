from typing import Dict, List

from pydantic import BaseModel


class EquipmentClassList(BaseModel):
    items: List[str]


class EquipmentSubclassList(BaseModel):
    items: List[str]


class EquipmentSubclassMap(BaseModel):
    items: Dict[str, List[str]]


class PowerFactorOut(BaseModel):
    submodule: str
    equipment_class: str
    sub_class: str | None = None
    active_power_w: float
    standby_power_w: float
