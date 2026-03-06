"""Building room lookup repository compatibility aliases."""

from app.repositories.building_room_repo import BuildingRoomRepository


class BuildingRoomLookupRepository(BuildingRoomRepository):
    """Compatibility alias for the building room lookup repository."""
