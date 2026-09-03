<template>
  <!-- Reads as a table: full-width striped rows carry the eye from the
       category across to its field, the way the Calculator tables do. -->
  <div class="headcount-table">
    <div
      v-for="row in rows"
      :key="row.sius_code"
      class="headcount-table__row row items-center no-wrap"
    >
      <!-- Canonical SIUS-category labels from the planner_headcount taxonomy
           vocabulary (#2613) — same backend source the Calculator uses. -->
      <label :for="`fte-${row.sius_code}`" class="col text-body2">
        {{ plannerHeadcountRowLabel(row.sius_code, vocab[row.sius_code], t) }}
      </label>
      <q-input
        :id="`fte-${row.sius_code}`"
        v-model.number="row.fte"
        class="headcount-table__input"
        type="number"
        outlined
        dense
        hide-bottom-space
        min="0"
        :step="fteStep"
        input-class="text-right"
        :rules="fteRules"
        :disable="disable || savingCode === row.sius_code"
        :loading="savingCode === row.sius_code"
        @blur="save(row)"
        @keyup.enter="save(row)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

import { api } from '@/api/http';
import { getDataEntryTaxonomy } from '@/api/taxonomies';
import {
  moduleInputDecimals,
  moduleInputStep,
  roundModuleInput,
} from '@/constant/input-decimals';
import { MODULES } from '@/constant/modules';
import {
  PLANNER_HEADCOUNT_CODES as HEADCOUNT_CODES,
  PLANNER_HEADCOUNT_SUBMODULE,
  plannerHeadcountRowLabel,
} from '@/constant/planner-headcount';
import { useModuleStore } from '@/stores/modules';
import { getNumericRules } from '@/utils/numeric-rules';

interface HeadcountRow {
  sius_code: string;
  fte: number | null;
  entryId: number | null;
}

interface SubmoduleItem {
  id: number;
  sius_code?: string;
  fte?: number | null;
}

const props = defineProps<{
  carbonReportId: number;
  year: string | number;
  disable: boolean;
}>();

const $q = useQuasar();
const { t, locale } = useI18n();
const moduleStore = useModuleStore();

const rows = ref<HeadcountRow[]>(
  HEADCOUNT_CODES.map((code) => ({
    sius_code: code,
    fte: null,
    entryId: null,
  })),
);
const savingCode = ref<string | null>(null);
const fteStep = moduleInputStep(MODULES.Headcount);
const fteRules = getNumericRules(
  { min: 0, maxDecimals: moduleInputDecimals(MODULES.Headcount) },
  t,
);

// SIUS code → request-locale label, from the planner_headcount taxonomy
// vocabulary (#2613). The students row has no code and keeps its i18n key.
const vocab = ref<Record<string, string>>({});

async function loadVocab() {
  try {
    const taxonomy = await getDataEntryTaxonomy(
      MODULES.Headcount,
      PLANNER_HEADCOUNT_SUBMODULE,
      props.year,
    );
    const map: Record<string, string> = {};
    taxonomy.children?.forEach((node) => {
      if (node.name && node.label) map[node.name] = node.label;
    });
    vocab.value = map;
  } catch {
    // Grid stays usable with bare codes; labels arrive on the next load.
  }
}

// Sanctioned side-effect bridge: the vocabulary is fetched in the request
// locale, so a language switch refetches it (same pattern as ModuleTable).
watch(locale, loadVocab);

const basePath = () =>
  `carbon-reports/${props.carbonReportId}/modules/headcount/${PLANNER_HEADCOUNT_SUBMODULE}`;

async function load() {
  try {
    const res = await api
      .get(`${basePath()}?page=1&limit=100`)
      .json<{ items: SubmoduleItem[] }>();
    const byCode = new Map(
      res.items
        .filter((it) => it.sius_code)
        .map((it) => [it.sius_code as string, it]),
    );
    rows.value = HEADCOUNT_CODES.map((code) => {
      const item = byCode.get(code);
      return {
        sius_code: code,
        fte:
          item?.fte == null
            ? null
            : roundModuleInput(MODULES.Headcount, item.fte),
        entryId: item?.id ?? null,
      };
    });
  } catch {
    // Empty module → no rows yet; leave the blank inputs.
  }
}

async function save(row: HeadcountRow) {
  const fte =
    typeof row.fte === 'number' && !Number.isNaN(row.fte) ? row.fte : null;
  // Nothing to persist: still-empty row.
  if (fte === null && row.entryId === null) return;
  if (fteRules.some((rule) => rule(fte) !== true)) return;
  savingCode.value = row.sius_code;
  try {
    if (row.entryId === null) {
      const created = await api
        .post(basePath(), { json: { sius_code: row.sius_code, fte } })
        .json<{ id: number }>();
      row.entryId = created.id;
    } else {
      await api.patch(`${basePath()}/${row.entryId}`, { json: { fte } }).json();
    }
  } catch {
    $q.notify({ type: 'negative', message: t('planner_headcount_save_error') });
    return;
  } finally {
    savingCode.value = null;
  }
  await moduleStore.refreshEmissionBreakdownIfNeeded();
}

onMounted(() => {
  void load();
  void loadVocab();
});
</script>

<style scoped lang="scss">
@use '@/css/02-tokens' as tokens;

.headcount-table {
  &__row {
    gap: tokens.$spacing-lg;
    padding: tokens.$spacing-xs tokens.$spacing-md;
    background-color: tokens.$table-bg-odd;

    &:nth-child(even) {
      background-color: tokens.$table-bg-even;
    }
  }

  &__input {
    width: tokens.$planner-grid-fte-input-width;

    // The field keeps its own white surface so it stays legible on the
    // shaded stripes instead of picking up the row behind it.
    :deep(.q-field__control) {
      background-color: tokens.$table-bg-odd;
    }
  }
}
</style>
