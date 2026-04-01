<script setup lang="ts">
import { computed } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

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
