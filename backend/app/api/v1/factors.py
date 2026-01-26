from fastapi import APIRouter

# from sqlmodel.ext.asyncio.session import AsyncSession

# from app.api.deps import get_db
# from app.schemas.factor import FactorRead

router = APIRouter()


# to be reimplemented later

# @router.get("/{submodule}/classes", response_model=list[str])


# @router.get(
#     "/{submodule}/classes/{equipment_class:path}/subclasses",
#     response_model=list[str],
# )


@router.get(
    "/{submodule}/class-subclass-map",
    response_model=dict[str, list[str]],
)
async def get_class_subclass_map(submodule: str):
    """Get mapping of equipment classes to subclasses for a given submodule."""
    # Implementation to be added later
    return {}


@router.get(
    "/{submodule}/classes/{equipment_class:path}/power",
    response_model=dict[str, float],
)
async def get_power_factor(
    submodule: str,
    equipment_class: str,
):
    """Get power factor for a given equipment class in a submodule."""
    # Implementation to be added later
    return None
