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
    topic: t('documentation_editing_rows_my_lab_topic'),
    description: t('documentation_editing_rows_my_lab_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/my_lab.ts',
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
    topic: t('documentation_editing_rows_infrastructure_topic'),
    description: t('documentation_editing_rows_infrastructure_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/infrastructure.ts',
  },
  {
    topic: t('documentation_editing_rows_equipment_electric_consumption_topic'),
    description: t(
      'documentation_editing_rows_equipment_electric_consumption_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/equipment_electric_consumption.ts',
  },
  {
    topic: t('documentation_editing_rows_purchase_topic'),
    description: t('documentation_editing_rows_purchase_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/purchase.ts',
  },
  {
    topic: t('documentation_editing_rows_internal_services_topic'),
    description: t('documentation_editing_rows_internal_services_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/internal_services.ts',
  },
  {
    topic: t('documentation_editing_rows_external_cloud_topic'),
    description: t('documentation_editing_rows_external_cloud_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/external_cloud.ts',
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
]);

const docRows = computed(() => [
  {
    topic: t('documentation_editing_calculator_user_documentation_title'),
    description: t(
      'documentation_editing_calculator_user_documentation_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator-user-doc/tree/main/docs',
  },
  {
    topic: t('documentation_editing_calculator_backoffice_documentation_title'),
    description: t(
      'documentation_editing_calculator_backoffice_documentation_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator-back-office-doc/tree/main/docs',
  },
  {
    topic: t('documentation_editing_calculator_developer_documentation_title'),
    description: t(
      'documentation_editing_calculator_developer_documentation_description',
    ),
    githubUrl: 'https://github.com/EPFL-ENAC/co2-calculator/tree/main/docs/src',
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
    <navigation-header
      :item="BACKOFFICE_NAV.BACKOFFICE_DOCUMENTATION_EDITING"
    />
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
                  class="text-weight-medium"
                  :href="props.row.githubUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                />
              </q-td>
            </q-tr>
          </template>
        </q-table>
        <h1 class="text-h2 q-mb-sm">
          {{ $t('documentation_editing_documentation_title') }}
        </h1>
        <div class="text-body1 q-mb-xl">
          {{ $t('documentation_editing_documentation_description_part_1') }}
          <a
            :href="
              $t('documentation_editing_documentation_description_link_url')
            "
            target="_blank"
            rel="noopener noreferrer"
          >
            {{
              $t('documentation_editing_documentation_description_link_text')
            }} </a
          >{{ $t('documentation_editing_documentation_description_part_2') }}
        </div>
        <q-table
          flat
          class="co2-table border table-spacing"
          :rows="docRows"
          :columns="columns"
          hide-pagination
          :pagination="{ rowsPerPage: 0 }"
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
                  class="text-weight-medium"
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
</style>
