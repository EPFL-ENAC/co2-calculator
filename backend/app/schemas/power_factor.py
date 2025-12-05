from typing import List

from pydantic import BaseModel


class EquipmentClassList(BaseModel):
    items: List[str]


class EquipmentSubclassList(BaseModel):
    items: List[str]
