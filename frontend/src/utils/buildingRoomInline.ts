import type { BuildingRoom } from '@/api/building_rooms';

/**
 * #2501 — inline editing of a buildings room row.
 *
 * The factor taxonomy's subkinds are room *types*, so the Local column's
 * options must come from the `BuildingRoom` ref-data of the row's current
 * building instead.
 */
export function buildingRoomOptions(
  rooms: BuildingRoom[],
): Array<{ value: string; label: string }> {
  return rooms.map((r) => ({ value: r.room_name, label: r.room_name }));
}

/**
 * Picking a room also carries its ref-data room_type (the form dialog's
 * autofill, normalized the same way) — without it the row would keep the
 * old room's type.
 */
export function buildingRoomPatchPayload(
  roomName: string | number | null,
  rooms: BuildingRoom[],
): Record<string, string | null> {
  const room = rooms.find((r) => r.room_name === roomName);
  return {
    room_name: roomName == null ? null : String(roomName),
    room_type: room?.room_type ? room.room_type.trim().toLowerCase() : null,
  };
}
