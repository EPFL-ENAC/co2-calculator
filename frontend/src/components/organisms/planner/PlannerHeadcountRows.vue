<template>
  <!-- Reads as a table: full-width striped rows carry the eye from the
       category across to its field, the way the Calculator tables do. -->
  <div class="headcount-table">
    <div
      v-for="row in rows"
      :key="row.sius_code"
      class="headcount-table__row row items-center no-wrap"
    >
      <!-- Canonical SIUS-category labels from i18n/headcount_factor.ts
           (keyed by the bare code) — same source the Calculator uses. -->
      <label :for="`fte-${row.sius_code}`" class="col text-body2">
        {{ $t(plannerHeadcountLabelKey(row.sius_code)) }}
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
        step="0.5"
        input-class="text-right"
        :disable="disable || savingCode === row.sius_code"
        :loading="savingCode === row.sius_code"
        @blur="save(row)"
        @keyup.enter="save(row)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useQuasar } from 'quasar';
import { useI18n } from 'vue-i18n';

import { api } from 'src/api/http';
import {
  PLANNER_HEADCOUNT_CODES as HEADCOUNT_CODES,
  PLANNER_HEADCOUNT_SUBMODULE,
  plannerHeadcountLabelKey,
} from 'src/constant/planner-headcount';

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
  disable: boolean;
}>();

const $q = useQuasar();
const { t } = useI18n();

const rows = ref<HeadcountRow[]>(
  HEADCOUNT_CODES.map((code) => ({
    sius_code: code,
    fte: null,
    entryId: null,
  })),
);
const savingCode = ref<string | null>(null);

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
        fte: item?.fte ?? null,
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
  } finally {
    savingCode.value = null;
  }
}

onMounted(load);
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

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
