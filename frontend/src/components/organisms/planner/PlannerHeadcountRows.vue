<template>
  <div class="q-gutter-y-sm">
    <div
      v-for="row in rows"
      :key="row.sius_code"
      class="row items-center justify-between q-py-xs"
    >
      <!-- Canonical SIUS-category labels from i18n/headcount_factor.ts
           (keyed by the bare code) — same source the Calculator uses. -->
      <div class="text-body1">{{ $t(row.sius_code) }}</div>
      <q-input
        v-model.number="row.fte"
        type="number"
        outlined
        dense
        min="0"
        step="0.5"
        style="max-width: 180px"
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
  PLANNER_HEADCOUNT_SUBMODULE,
  PLANNER_SIUS_CODES as SIUS_CODES,
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
  SIUS_CODES.map((code) => ({ sius_code: code, fte: null, entryId: null })),
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
    rows.value = SIUS_CODES.map((code) => {
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
