<script setup lang="ts">
import { computed } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const rows = computed(() => [
  {
    topic: t('documentation_editing_rows_common_topic'),
    description: t('documentation_editing_rows_common_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/common.ts',
  },
  {
    topic: t('documentation_editing_rows_headcount_topic'),
    description: t('documentation_editing_rows_headcount_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/headcount.ts',
  },
  {
    topic: t('documentation_editing_rows_process_emissions_topic'),
    description: t('documentation_editing_rows_process_emissions_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/process_emissions.ts',
  },
  {
    topic: t('documentation_editing_rows_buildings_topic'),
    description: t('documentation_editing_rows_buildings_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/buildings.ts',
  },
  {
    topic: t('documentation_editing_rows_equipment_topic'),
    description: t('documentation_editing_rows_equipment_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/equipment.ts',
  },
  {
    topic: t('documentation_editing_rows_external_cloud_topic'),
    description: t('documentation_editing_rows_external_cloud_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/external_cloud.ts',
  },
  {
    topic: t('documentation_editing_rows_professional_travel_topic'),
    description: t(
      'documentation_editing_rows_professional_travel_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/professional_travel.ts',
  },
  {
    topic: t('documentation_editing_rows_purchase_topic'),
    description: t('documentation_editing_rows_purchase_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/purchase.ts',
  },
  {
    topic: t('documentation_editing_rows_research_facilities_topic'),
    description: t(
      'documentation_editing_rows_research_facilities_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/research_facilities.ts',
  },
  {
    topic: t('documentation_editing_rows_tooltips_topic'),
    description: t('documentation_editing_rows_tooltips_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/tooltips.ts',
  },
  {
    topic: t('documentation_editing_rows_backoffice_topic'),
    description: t('documentation_editing_rows_backoffice_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/backoffice.ts',
  },
  {
    topic: t('documentation_editing_rows_admin_topic'),
    description: t('documentation_editing_rows_admin_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/admin.ts',
  },
  {
    topic: t('documentation_editing_rows_backoffice_data_management_topic'),
    description: t(
      'documentation_editing_rows_backoffice_data_management_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/backoffice_data_management.ts',
  },
  {
    topic: t(
      'documentation_editing_rows_backoffice_documentation_editing_topic',
    ),
    description: t(
      'documentation_editing_rows_backoffice_documentation_editing_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/backoffice_documentation_editing.ts',
  },
  {
    topic: t('documentation_editing_rows_backoffice_reporting_topic'),
    description: t(
      'documentation_editing_rows_backoffice_reporting_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/backoffice_reporting.ts',
  },
  {
    topic: t('documentation_editing_rows_backoffice_user_management_topic'),
    description: t(
      'documentation_editing_rows_backoffice_user_management_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/backoffice_user_management.ts',
  },
  {
    topic: t('documentation_editing_rows_home_topic'),
    description: t('documentation_editing_rows_home_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/home.ts',
  },
  {
    topic: t('documentation_editing_rows_login_topic'),
    description: t('documentation_editing_rows_login_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/login.ts',
  },
  {
    topic: t('documentation_editing_rows_results_topic'),
    description: t('documentation_editing_rows_results_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/results.ts',
  },
  {
    topic: t('documentation_editing_rows_workspace_setup_topic'),
    description: t('documentation_editing_rows_workspace_setup_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/workspace_setup.ts',
  },
  {
    topic: t('documentation_editing_rows_simulation_topic'),
    description: t('documentation_editing_rows_simulation_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/simulation.ts',
  },
  {
    topic: t('documentation_editing_rows_calculator_update_topic'),
    description: t('documentation_editing_rows_calculator_update_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/calculator_update.ts',
  },
]);

const columns: QTableColumn[] = [
  {
    name: 'topic',
    label: t('documentation_editing_table_label_topic'),
    field: 'topic',
    align: 'left',
  },
  {
    name: 'description',
    label: t('documentation_editing_table_label_description'),
    field: 'description',
    align: 'left',
  },
  {
    name: 'githubUrl',
    label: t('documentation_editing_table_label_documentation'),
    field: 'githubUrl',
    align: 'right',
  },
];
</script>

<template>
  <q-page class="q-mb-xl">
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_UI_TEXTS_EDITING" />
    <div class="page q-pl-md">
      <div class="q-mt-xl q-mx-lg">
        <h1 class="text-h2 q-mb-sm">
          {{ $t('documentation_editing_translation_title') }}
        </h1>
        <div class="text-body1 q-mb-xl">
          {{ $t('documentation_editing_translation_description_part_1') }}
          <a
            :href="$t('documentation_editing_translation_description_link_url')"
            target="_blank"
            rel="noopener noreferrer"
          >
            {{
              $t('documentation_editing_translation_description_link_text')
            }} </a
          >{{ $t('documentation_editing_translation_description_part_2') }}
        </div>
        <q-table
          flat
          class="co2-table border table-spacing"
          :rows="rows"
          :columns="columns"
          hide-pagination
          :pagination="{ rowsPerPage: 0 }"
          :no-data-label="$t('common_no_items')"
          :rows-per-page-label="$t('rows_per_page')"
        >
          <template #body="props">
            <q-tr :props="props" class="q-tr--no-hover">
              <q-td key="topic" :props="props">
                {{ props.row.topic }}
              </q-td>
              <q-td key="description" :props="props">
                {{ props.row.description }}
              </q-td>
              <q-td key="githubUrl" :props="props">
                <q-btn
                  icon="o_article"
                  color="grey-4"
                  text-color="primary"
                  :label="$t('documentation_editing_edit_on_github')"
                  unelevated
                  no-caps
                  outline
                  size="sm"
                  class="text-weight-medium github-btn"
                  :href="props.row.githubUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                />
              </q-td>
            </q-tr>
          </template>
        </q-table>
      </div>
    </div>
  </q-page>
</template>

<style scoped lang="scss">
.page {
  max-width: 1320px;
}
</style>

<style scoped lang="scss">
.table-spacing {
  margin-top: 24px;
  margin-bottom: 40px;
}

.github-btn :deep(.q-btn__content) {
  flex-wrap: nowrap;
}
</style>

<!-- Not scoped: .co2-table's rules reach into Quasar's rendered table internals
     (thead/tbody/td/tr), which do not receive scoped style attributes. -->
<style lang="scss">
@use 'src/css/02-tokens' as tokens;

.co2-table {
  border: 1px solid tokens.$container-default-border;
  border-radius: tokens.$table-border-radius;
  font-size: tokens.$text-size-sm;

  /* height or max-height is important for sticky header */
  max-height: tokens.$table-max-height;
  overflow-y: auto;

  th {
    font-size: tokens.$text-size-sm;
  }

  thead tr th {
    position: sticky;
    z-index: tokens.$table-header-z-index;
    background-color: tokens.$table-bg-odd;
  }

  thead tr:first-child th {
    top: 0;
  }

  .q-table td {
    border: none;
  }

  tbody .q-tr:nth-child(even) {
    background-color: tokens.$table-bg-even;
  }

  tr {
    &::before {
      display: none !important;
    }
  }

  &--selectable {
    tbody tr {
      cursor: pointer;

      &.selected > td {
        border-top: 1px solid tokens.$container-selected-hover-border !important;
        border-bottom: 1px solid tokens.$container-selected-hover-border !important;
      }

      &.selected:first-child > td {
        border-top: none !important;
        border-bottom: 1px solid tokens.$container-selected-hover-border !important;
      }

      &.selected:last-child > td {
        border-top: 1px solid tokens.$container-selected-hover-border !important;
        border-bottom: none !important;
      }
    }
  }

  .square-button {
    padding: tokens.$spacing-sm tokens.$spacing-sm;
  }
}
</style>
