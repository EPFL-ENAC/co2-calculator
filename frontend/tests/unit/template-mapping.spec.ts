/**
 * Regression test for the "Download CSV template" button (#2026).
 *
 * The button shows on every module table, and its click handler silently
 * returns when getTemplateFileName finds no entry. That is exactly how
 * the research facilities button broke: both submodule tables shipped
 * with #2007, but the template map never got their entries, so the click
 * did nothing and no one saw an error.
 *
 * The list below mirrors the submodule tables declared in
 * src/constant/module-config/. Every one of them must resolve to a
 * template file that ships in public/templates. When you add a submodule
 * table, add it here and map its template.
 */
import { existsSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';

import { test, expect } from '@playwright/test';

import {
  MODULES,
  SUBMODULE_BUILDINGS_TYPES,
  SUBMODULE_EQUIPMENT_TYPES,
  SUBMODULE_EXTERNAL_CLOUD_TYPES,
  SUBMODULE_HEADCOUNT_TYPES,
  SUBMODULE_PROCESSES_TYPES,
  SUBMODULE_PROFESSIONAL_TRAVEL_TYPES,
  SUBMODULE_PURCHASE_TYPES,
  SUBMODULE_RESEARCH_FACILITIES_TYPES,
} from '../../src/constant/modules';
import type { AllSubmoduleTypes, Module } from '../../src/constant/modules';
import { getTemplateFileName } from '../../src/constant/templateMapping';

const TEMPLATES_DIR = join(
  dirname(fileURLToPath(import.meta.url)),
  '../../public/templates',
);

const TABLE_COMBOS: [Module, AllSubmoduleTypes][] = [
  [MODULES.Headcount, SUBMODULE_HEADCOUNT_TYPES.Member],
  [MODULES.ProfessionalTravel, SUBMODULE_PROFESSIONAL_TRAVEL_TYPES.Plane],
  [MODULES.ProfessionalTravel, SUBMODULE_PROFESSIONAL_TRAVEL_TYPES.Train],
  [MODULES.Buildings, SUBMODULE_BUILDINGS_TYPES.Building],
  [MODULES.Buildings, SUBMODULE_BUILDINGS_TYPES.EnergyCombustion],
  [MODULES.Equipment, SUBMODULE_EQUIPMENT_TYPES.Scientific],
  [MODULES.Equipment, SUBMODULE_EQUIPMENT_TYPES.IT],
  [MODULES.Equipment, SUBMODULE_EQUIPMENT_TYPES.Other],
  [MODULES.Purchase, SUBMODULE_PURCHASE_TYPES.ScientificEquipmentPurchases],
  [MODULES.Purchase, SUBMODULE_PURCHASE_TYPES.ITEquipmentPurchases],
  [MODULES.Purchase, SUBMODULE_PURCHASE_TYPES.ConsumablePurchases],
  [MODULES.Purchase, SUBMODULE_PURCHASE_TYPES.BioProductPurchases],
  [MODULES.Purchase, SUBMODULE_PURCHASE_TYPES.ServicePurchases],
  [MODULES.Purchase, SUBMODULE_PURCHASE_TYPES.VehiclePurchases],
  [MODULES.Purchase, SUBMODULE_PURCHASE_TYPES.OtherPurchases],
  [MODULES.Purchase, SUBMODULE_PURCHASE_TYPES.PurchasesCentralized],
  [MODULES.ExternalCloudAndAI, SUBMODULE_EXTERNAL_CLOUD_TYPES.external_clouds],
  [MODULES.ExternalCloudAndAI, SUBMODULE_EXTERNAL_CLOUD_TYPES.external_ai],
  [MODULES.ProcessEmissions, SUBMODULE_PROCESSES_TYPES.ProcessEmissions],
  [
    MODULES.ResearchFacilities,
    SUBMODULE_RESEARCH_FACILITIES_TYPES.ResearchFacilities,
  ],
  [
    MODULES.ResearchFacilities,
    SUBMODULE_RESEARCH_FACILITIES_TYPES.AnimalFacilities,
  ],
];

for (const [moduleType, submoduleType] of TABLE_COMBOS) {
  test(`${moduleType}:${submoduleType} maps to a shipped template`, () => {
    const fileName = getTemplateFileName(moduleType, submoduleType);
    expect(fileName, 'download button resolves to no template').toBeTruthy();
    expect(
      existsSync(join(TEMPLATES_DIR, fileName as string)),
      `${fileName} is not in public/templates`,
    ).toBe(true);
  });
}
