from typing import Protocol

from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.data_entry import DataEntry, DataEntryTypeEnum
from app.models.module_type import DERIVED_DATA_ENTRY_TYPES
from app.workflows.embodied_energy import EmbodiedEnergyWorkflow


class DerivedEntryWorkflow(Protocol):
    def __init__(self, session: AsyncSession): ...

    async def create_derived_entries_for(
        self, parent_entries: list[DataEntry]
    ) -> int: ...


DERIVED_ENTRY_WORKFLOWS: dict[DataEntryTypeEnum, type[DerivedEntryWorkflow]] = {
    DataEntryTypeEnum.building_embodied_energy: EmbodiedEnergyWorkflow,
}

_missing = {
    derived
    for derived_list in DERIVED_DATA_ENTRY_TYPES.values()
    for derived in derived_list
} - DERIVED_ENTRY_WORKFLOWS.keys()
if _missing:
    raise RuntimeError(
        "DERIVED_DATA_ENTRY_TYPES declares derived types without a workflow "
        f"in DERIVED_ENTRY_WORKFLOWS: {sorted(t.name for t in _missing)}"
    )
