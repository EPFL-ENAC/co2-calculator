<script setup lang="ts">
import { computed } from 'vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const planColumns = computed<QTableColumn[]>(() => [
  {
    name: 'name',
    label: t('planner_table_name'),
    field: 'name',
    align: 'left',
    sortable: true,
  },
  {
    name: 'date',
    label: t('planner_table_date'),
    field: 'date',
    align: 'left',
    sortable: true,
  },
  {
    name: 'creator',
    label: t('planner_table_creator'),
    field: 'creator',
    align: 'left',
    sortable: true,
  },
  {
    name: 'tco2eq',
    label: t('tco2eq'),
    field: 'tco2eq',
    align: 'right',
    sortable: true,
  },
  {
    name: 'action',
    label: t('planner_table_action'),
    field: 'action',
    align: 'right',
  },
]);

// PLACEHOLDER: TO BE DELETED WHEN PLAN ROWS ARE POPULATED
const planRows = [
  {
    name: 'Scientific Grant H',
    date: '21-03-2026',
    creator: 'Charlie Weil',
    tco2eq: "2'543",
  },
  {
    name: 'Big Buying year',
    date: '15-04-2026',
    creator: 'Benjamin Botros',
    tco2eq: "3'301",
  },
  {
    name: 'Unit reorganisation',
    date: '04-05-2026',
    creator: 'Pierre Guilbart',
    tco2eq: "1'201",
  },
  {
    name: 'Change of leadership 2027',
    date: '04-06-2026',
    creator: 'Andrina Beuggert',
    tco2eq: "5'500",
  },
];
</script>

<template>
  <section class="co2-project-planner">
    <div class="co2-project-planner__inner">
      <div class="row items-start justify-between no-wrap q-mb-md">
        <div class="row items-center q-gutter-sm">
          <q-icon name="o_calendar_month" size="md" color="info" />
          <h2 class="text-h3 q-mb-none">
            {{ $t('co2_project_planner_title') }}
          </h2>
          <q-badge color="info" class="text-weight-bold planner-count">
            {{ planRows.length }}
          </q-badge>
        </div>
        <q-btn
          color="info"
          :label="$t('co2_project_planner_btn')"
          icon="o_add"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
          :to="{ name: 'project-planner' }"
        />
      </div>

      <p class="text-body1 section-intro q-mb-lg">
        {{ $t('co2_project_planner_description') }}
      </p>

      <q-table
        flat
        dense
        class="co2-table"
        :columns="planColumns"
        :rows="planRows"
        row-key="name"
        hide-pagination
        :rows-per-page-options="[0]"
        :no-data-label="$t('common_no_items')"
        :rows-per-page-label="$t('rows_per_page')"
      >
        <template #header="scope">
          <q-tr :props="scope">
            <q-th
              v-for="col in scope.cols"
              :key="col.name"
              :props="scope"
              :align="col.align"
              class="q-pa-xs"
            >
              {{ col.label }}
            </q-th>
          </q-tr>
        </template>
        <template #body="props">
          <q-tr :props="props" class="q-tr--no-hover">
            <q-td
              v-for="col in props.cols"
              :key="col.name"
              :props="props"
              :align="col.align"
              class="q-pa-xs"
            >
              <template v-if="col.name === 'action'">
                <div class="row no-wrap justify-end q-gutter-xs">
                  <q-btn
                    icon="o_content_copy"
                    color="grey-4"
                    text-color="primary"
                    unelevated
                    no-caps
                    dense
                    outline
                    square
                    size="xs"
                    class="square-button"
                  />
                  <q-btn
                    icon="o_edit"
                    color="grey-4"
                    text-color="primary"
                    unelevated
                    no-caps
                    dense
                    outline
                    square
                    size="xs"
                    class="square-button"
                  />
                  <q-btn
                    icon="o_delete"
                    color="grey-4"
                    text-color="primary"
                    unelevated
                    no-caps
                    dense
                    outline
                    square
                    size="xs"
                    class="square-button"
                  />
                </div>
              </template>
              <template v-else>{{ props.row[col.field] }}</template>
            </q-td>
          </q-tr>
        </template>
      </q-table>
    </div>
  </section>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

// Full-width grey band spanning the whole content area (sits outside the
// centred page-grid); its inner content stays aligned with the page width.
.co2-project-planner {
  width: 100%;
  background-color: var(--q-grey-1, #f5f5f5);
  padding: 3.5rem 0;
}

.co2-project-planner__inner {
  max-width: tokens.$layout-page-width;
  margin: 0 auto;
  padding: 0 tokens.$layout-page-padding-x;
}

// Intro/description text under a section title is capped at three-quarters width.
.section-intro {
  max-width: 75%;
}

// Perfect-circle count badge next to the title.
.planner-count {
  width: 1.5rem;
  height: 1.5rem;
  padding: 0;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}
</style>
