<template>
  <q-page class="page-grid">
    <q-card flat class="container">
      <q-icon
        name="o_display_settings"
        color="accent"
        size="32px"
        class="q-mb-md"
      />
      <h1 class="text-h2 q-mb-md">{{ $t('simulation_title') }}</h1>
      <p class="text-body1 q-mb-none">{{ $t('simulation_intro') }}</p>
    </q-card>

    <q-card flat class="container container--pa-none q-my-xl">
      <div class="row">
        <div
          class="col q-pa-xl cursor-pointer simulation-tab"
          :class="{ 'simulation-tab--active': activeTab === 'explore' }"
          @click="activeTab = 'explore'"
        >
          <div class="row items-center q-gutter-sm">
            <q-icon
              name="o_manage_search"
              size="sm"
              :color="activeTab === 'explore' ? 'accent' : 'secondary'"
            />
            <span
              class="text-h4 text-weight-bold"
              :class="activeTab === 'explore' ? '' : 'text-secondary'"
              >{{ $t('simulation_tab_explore') }}</span
            >
          </div>
          <p
            class="text-body2 q-mt-xs q-mb-none"
            :class="activeTab === 'explore' ? 'text-secondary' : 'text-grey-4'"
          >
            {{ $t('simulation_tab_explore_subtitle') }}
          </p>
        </div>

        <q-separator vertical />

        <div
          class="col q-pa-xl cursor-pointer simulation-tab"
          :class="{ 'simulation-tab--active': activeTab === 'plan' }"
          @click="activeTab = 'plan'"
        >
          <div class="row items-center q-gutter-sm">
            <q-icon
              name="o_calendar_month"
              size="sm"
              :color="activeTab === 'plan' ? 'accent' : 'secondary'"
            />
            <span
              class="text-h4 text-weight-bold"
              :class="activeTab === 'plan' ? '' : 'text-secondary'"
              >{{ $t('simulation_tab_plan') }}</span
            >
          </div>
          <p
            class="text-body2 q-mt-xs q-mb-none"
            :class="activeTab === 'plan' ? 'text-secondary' : 'text-grey-4'"
          >
            {{ $t('simulation_tab_plan_subtitle') }}
          </p>
        </div>
      </div>

      <q-separator />

      <div class="q-px-lg q-py-xl">
        <template v-if="activeTab === 'explore'">
          <h2 class="text-h3 q-mb-xs q-mt-lg">
            {{ $t('simulation_explore_title') }}
          </h2>
          <p class="text-body2 text-secondary q-mb-lg">
            {{ $t('simulation_explore_description') }}
          </p>
          <q-btn
            color="accent"
            :label="$t('simulation_explore_btn')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium"
          />
        </template>

        <template v-else>
          <div class="row items-start justify-between q-mb-xs q-mt-lg">
            <h2 class="text-h3">{{ $t('simulation_plan_title') }}</h2>
            <q-icon name="o_info" size="22px" color="primary" />
          </div>
          <p class="text-body2 text-secondary q-mb-lg col-6">
            {{ $t('simulation_plan_description') }}
          </p>
          <q-btn
            color="accent"
            :label="$t('simulation_plan_btn')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium q-mb-xl"
          />

          <q-table
            flat
            dense
            class="co2-table q-mt-lg"
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
        </template>
      </div>
    </q-card>
  </q-page>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import type { QTableColumn } from 'quasar';

const activeTab = ref<'explore' | 'plan'>('explore');

const planColumns: QTableColumn[] = [
  { name: 'name', label: 'Name', field: 'name', align: 'left', sortable: true },
  { name: 'date', label: 'Date', field: 'date', align: 'left', sortable: true },
  {
    name: 'creator',
    label: 'Creator',
    field: 'creator',
    align: 'left',
    sortable: true,
  },
  {
    name: 'tco2eq',
    label: 'tco2eq',
    field: 'tco2eq',
    align: 'right',
    sortable: true,
  },
  { name: 'action', label: 'Action', field: 'action', align: 'right' },
];

const planRows = [
  {
    name: 'SNSF Grant ABC',
    date: '21-03-2026',
    creator: 'Charlie Weil',
    tco2eq: "2'543",
  },
  {
    name: 'SNSF Grant ABC',
    date: '21-03-2026',
    creator: 'Charlie Weil',
    tco2eq: "2'543",
  },
];
</script>

<style scoped lang="scss">
.simulation-tab {
  background-color: var(--q-grey-1, #f5f5f5);
  border-bottom: 2px solid transparent;
  transition: background-color 0.2s;

  &--active {
    background-color: #ffffff;
    border-bottom: 2px solid var(--q-accent);
  }
}
</style>
