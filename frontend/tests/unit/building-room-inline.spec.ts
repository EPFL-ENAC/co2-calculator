/**
 * #2501 — inline edits on a buildings room row.
 *
 * The Local column's inline select used to be fed the factor taxonomy's
 * subkinds, which for buildings are room *types* ("auditoriums", …) — picking
 * one PATCHed `room_name: "auditoriums"`, an unknown room, and the emission
 * recompute 422ed. Options now come from `BuildingRoom` ref-data, and a room
 * pick packs the room's normalized `room_type` into the same PATCH so the row
 * can't keep the old room's type.
 */

import { test, expect } from '@playwright/test';

import type { BuildingRoom } from '../../src/api/building_rooms';
import {
  buildingRoomOptions,
  buildingRoomPatchPayload,
} from '../../src/utils/buildingRoomInline';

const ROOMS: BuildingRoom[] = [
  {
    building_location: 'Lausanne',
    building_name: 'BCH',
    room_name: 'BCH 1234',
    room_type: ' Office ',
    room_surface_square_meter: 43,
  },
  {
    building_location: 'Lausanne',
    building_name: 'BCH',
    room_name: 'BCH 2200',
    room_type: null,
    room_surface_square_meter: 12,
  },
];

test('options are the ref-data room names, not factor subkinds', () => {
  expect(buildingRoomOptions(ROOMS)).toEqual([
    { value: 'BCH 1234', label: 'BCH 1234' },
    { value: 'BCH 2200', label: 'BCH 2200' },
  ]);
});

test('a room pick packs its normalized room_type into the PATCH', () => {
  expect(buildingRoomPatchPayload('BCH 1234', ROOMS)).toEqual({
    room_name: 'BCH 1234',
    room_type: 'office',
  });
});

test('a room without a ref-data type patches room_type null', () => {
  expect(buildingRoomPatchPayload('BCH 2200', ROOMS)).toEqual({
    room_name: 'BCH 2200',
    room_type: null,
  });
});

test('clearing the room clears the type with it', () => {
  expect(buildingRoomPatchPayload(null, ROOMS)).toEqual({
    room_name: null,
    room_type: null,
  });
});
