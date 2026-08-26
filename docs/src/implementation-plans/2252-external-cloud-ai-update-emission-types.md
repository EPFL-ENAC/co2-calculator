---
status: delivered
issue: 2252
last_updated: 2026-08-26
title: "External AI — product-name categories replace vendor slugs"
summary: "The AI provider categories changed from vendor slugs (google, mistral_ai, anthropic, openai, cohere, others) to the product-name spellings the re-uploaded CSVs carry: Gemini (Google), Mistral AI, Claude (Anthropic), ChatGPT (OpenAI), Copilot (Microsoft), Copilot (GitHub), Other. _AI_USE_MAP now declares only the canonical tokens of those seven spellings; the legacy slug keys are deleted (the planned DB drop removes the data that used them). provider_cohere is removed from the taxonomy, registry, and IT breakdown — Cohere is no longer a category, and Copilot (Microsoft) resolves to the provider_microsoft leaf #2091 already added, not to a repurposed cohere slot. Results-chart subcategory labels are renamed to match, and the random dev seeders emit the new spellings."
---

# #2252 — External AI: product-name categories

## Why

The data manager replaced the AI factor/entry CSVs with product-name provider
categories. Resolution already accepted both spellings since #2091; this
change makes the new spellings the only ones (no backward-compatibility
paths), coordinated with a DB drop + re-upload agreed in the issue.

## What shipped

- `backend/app/modules/external_cloud_and_ai/emissions.py` — `_AI_USE_MAP`
  keeps only the canonical tokens of the seven shipped categories.
  `Copilot (Microsoft)` maps to `provider_microsoft` (not `provider_cohere`
  as the issue snippet suggested — that snippet predates #2091, which added
  dedicated microsoft/github leaves).
- `backend/app/modules/emissions/taxonomy.py` — `provider_cohere` (110205)
  deleted; other values unchanged. `registry.py` and `utils/it_breakdown.py`
  updated accordingly; `frontend/src/types/emission-taxonomy.gen.ts`
  regenerated.
- `frontend/src/i18n/results.ts` — chart subcategory labels renamed to the
  product names (en + fr); cohere label and its `charts.ts` mapping removed.
- Random dev seeders (`seed_factors.py`, `seed_data_entries.py`) emit the new
  spellings; `seed_factors` derives the emission type via `resolve_ai`.
- Integration rematch test seeds `ChatGPT (OpenAI)` instead of `openai`.
- Integration test
  `tests/integration/modules/external_cloud_and_ai/test_emission_type_resolution.py`
  pins that each of the seven categories (and each cloud service_type)
  resolves to its own leaf through the real
  `FactorResolver → resolve_emission_types → prepare_create` pipeline.
- Bug found by that test: `external_ai` sat in the static
  `DATA_ENTRY_TO_EMISSION_TYPES` map, which `resolve_emission_types`
  consults before `_RUNTIME_RESOLVERS` — so an AI entry produced one
  emission row per provider leaf (7 rows, same kg, ~7× total) instead of
  routing through `resolve_ai`. The static entry is removed (clouds
  already worked this way); the random seeder gets
  `external_ai: external__ai` in `_SEED_EMISSION_ROOTS` to keep seeding
  valid leaves.

The form/table provider dropdown needs no code change: its options derive
from factor classification via the taxonomy tree, so the re-uploaded factor
CSV renames it.

## Deploy coupling

Must deploy together with the DB drop/re-upload: rows persisted with
emission_type_id 110205 or old-slug providers fail hard (by design, #2091)
once this code runs.
