<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import type { ModuleConfig, Submodule } from 'src/constant/moduleConfig';
import { useAuthStore } from 'src/stores/auth';
import { useModuleStore } from 'src/stores/modules';
import { nOrDash } from 'src/utils/number';
import {
  buildPrintColumns,
  renderPrintCell,
  type PrintCellContext,
  type PrintRow,
} from 'src/utils/printTable';

interface Props {
  submodule: Submodule;
  moduleConfig: ModuleConfig;
  rows: PrintRow[];
  /** Institutional id → name. Absent in the planner, which has no roster. */
  headcountMembers?: Map<string, string>;
  /** Planner prefilled modules: add the reference kgCO₂eq and % columns. */
  showReferenceColumns?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  headcountMembers: () => new Map(),
  showReferenceColumns: false,
});

const { t, te } = useI18n();
const authStore = useAuthStore();
const moduleStore = useModuleStore();

const travelerNames = computed(() => {
  const map = new Map(props.headcountMembers);
  const institutionalId = authStore.user?.institutional_id;
  if (institutionalId && !map.has(institutionalId)) {
    map.set(institutionalId, authStore.displayName);
  }
  return map;
});

const translate = (key: string, params?: Record<string, unknown>) =>
  t(key, params ?? {});

const columns = computed(() =>
  buildPrintColumns(
    props.submodule.moduleFields,
    translate,
    props.showReferenceColumns,
  ),
);

const taxonomyKindLabels = computed<Record<string, string>>(() => {
  const taxo = moduleStore.state.taxonomySubmodule[props.submodule.id];
  const map: Record<string, string> = {};
  taxo?.children?.forEach((node) => {
    if (node.name && node.label) {
      if (node.translation_key && te(node.translation_key)) {
        map[node.name] = t(node.translation_key);
      } else if (te(node.name)) {
        map[node.name] = t(node.name);
      } else {
        map[node.name] = node.label;
      }
    }
  });
  return map;
});

const cellContext = computed<PrintCellContext>(() => ({
  t: translate,
  te,
  taxonomyKindLabels: taxonomyKindLabels.value,
  headcountMembers: travelerNames.value,
  formatNumber: (value: number, options?: Intl.NumberFormatOptions) =>
    nOrDash(value, { options }),
  numberFormatOptions: props.moduleConfig.numberFormatOptions,
}));
</script>

<template>
  <table class="print-table">
    <thead>
      <tr>
        <th
          v-for="col in columns"
          :key="col.name"
          :style="{ textAlign: col.align }"
        >
          {{ col.label }}
        </th>
      </tr>
    </thead>
    <tbody>
      <tr v-for="(row, idx) in rows" :key="String(row.id ?? idx)">
        <td
          v-for="col in columns"
          :key="col.name"
          :style="{ textAlign: col.align }"
        >
          {{ renderPrintCell(row, col, cellContext) }}
        </td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped lang="scss">
.print-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 9px;

  th,
  td {
    border: 1px solid var(--half-muted-color);
    padding: 2px 4px;
    word-break: break-word;
    vertical-align: top;
  }

  th {
    font-weight: 600;
  }

  thead {
    display: table-header-group;
  }

  tr {
    break-inside: avoid;
    page-break-inside: avoid;
  }
}
</style>
