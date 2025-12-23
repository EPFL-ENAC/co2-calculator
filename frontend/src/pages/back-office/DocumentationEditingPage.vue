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
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/mylab.ts',
  },
  {
    topic: t('documentation_editing_rows_professional_travel_topic'),
    description: t(
      'documentation_editing_rows_professional_travel_description',
    ),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/professionaltravel.ts',
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
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/equipmentelectricconsumption.ts',
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
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/internalservices.ts',
  },
  {
    topic: t('documentation_editing_rows_external_cloud_topic'),
    description: t('documentation_editing_rows_external_cloud_description'),
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator/blob/dev/frontend/src/i18n/externalcloud.ts',
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
]);

const documentationSections = [
  {
    title: 'documentation_editing_calculator_co2_documentation_title',
    description:
      'documentation_editing_calculator_co2_documentation_description',
  },
  {
    title: 'documentation_editing_calculator_backoffice_documentation_title',
    description:
      'documentation_editing_calculator_backoffice_documentation_description',
  },
  {
    title: 'documentation_editing_calculator_service_documentation_title',
    description:
      'documentation_editing_calculator_service_documentation_description',
  },
  {
    title: 'documentation_editing_calculator_developer_documentation_title',
    description:
      'documentation_editing_calculator_developer_documentation_description',
  },
];

const loremRows = computed(() => [
  {
    topic: t('documentation_editing_lorem_rows_topic'),
    description: t('documentation_editing_lorem_rows_description'),
    githubUrl: '#',
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
          {{ $t('documentation_editing_translation_description') }}
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
        <div>
          <h1 class="text-h2 q-mb-sm">
            {{ $t('documentation_editing_documentation_title') }}
          </h1>
          <p class="text-body1 q-mb-xl">
            {{ $t('documentation_editing_documentation_description') }}
          </p>
          <div v-for="section in documentationSections" :key="section.title">
            <h2 class="text-h3 q-mt-lg q-mb-sm">
              {{ $t(section.title) }}
            </h2>
            <p class="text-body1 q-mb-xl">
              {{ $t(section.description) }}
            </p>
            <q-table
              flat
              class="co2-table border table-spacing"
              :rows="loremRows"
              :columns="columns"
              hide-pagination
            >
              <template #body="props">
                <q-tr :props="props">
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
