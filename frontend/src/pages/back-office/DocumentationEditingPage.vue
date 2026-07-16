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
    docUrl: 'https://epfl-enac.github.io/co2-calculator-user-doc/',
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator-user-doc/tree/main/docs',
  },
  {
    topic: t('documentation_editing_calculator_backoffice_documentation_title'),
    description: t(
      'documentation_editing_calculator_backoffice_documentation_description',
    ),
    docUrl: 'https://epfl-enac.github.io/co2-calculator-back-office-doc/',
    githubUrl:
      'https://github.com/EPFL-ENAC/co2-calculator-back-office-doc/tree/main/docs',
  },
  {
    topic: t('documentation_editing_calculator_developer_documentation_title'),
    description: t(
      'documentation_editing_calculator_developer_documentation_description',
    ),
    docUrl: '/docs/',
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
          :no-data-label="$t('common_no_items')"
          :rows-per-page-label="$t('rows_per_page')"
        >
          <template #body="props">
            <q-tr :props="props" class="q-tr--no-hover">
              <q-td key="topic" :props="props">
                <a
                  :href="props.row.docUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {{ props.row.topic }}
                </a>
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
