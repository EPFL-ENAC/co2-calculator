<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import type { QTableColumn } from 'quasar';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter } from 'vue-router';

import {
  useSimulatorPlansStore,
  type SimulatorPlan,
} from 'src/stores/simulatorPlans';
import { useWorkspaceStore } from 'src/stores/workspace';
import { parseUtcDate } from 'src/utils/date';

const { t, locale } = useI18n();
const route = useRoute();
const router = useRouter();
const workspaceStore = useWorkspaceStore();
const plansStore = useSimulatorPlansStore();

// workspaceGuard ensures selectedUnit is always set before the home page
// renders (same invariant as SimulationExplorePage).
const unitId = computed(() => workspaceStore.selectedUnit!.id);

const creating = ref(false);
const confirmDelete = ref(false);
const planToDelete = ref<SimulatorPlan | null>(null);

function formatPlanDate(dateString: string | null): string {
  if (!dateString) return '';
  return parseUtcDate(dateString).toLocaleDateString(locale.value);
}

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
    field: 'created_at',
    align: 'left',
    sortable: true,
    format: (val) => formatPlanDate(val as string | null),
  },
  {
    name: 'creator',
    label: t('planner_table_creator'),
    field: 'creator_name',
    align: 'left',
    sortable: true,
  },
  {
    name: 'tco2eq',
    label: t('tco2eq'),
    field: () => '',
    align: 'right',
  },
  {
    name: 'action',
    label: t('planner_table_action'),
    field: 'action',
    align: 'right',
  },
]);

async function refresh() {
  await plansStore.fetchPlans(unitId.value);
}

async function onStartProject() {
  if (creating.value) return;
  creating.value = true;
  try {
    const plan = await plansStore.createPlan(unitId.value);
    await router.push({
      name: 'project-planner',
      params: { ...route.params, name: plan.name },
    });
  } finally {
    creating.value = false;
  }
}

async function onDuplicate(row: SimulatorPlan) {
  await plansStore.duplicatePlan(row.id);
  await refresh();
}

function onEdit(row: SimulatorPlan) {
  void router.push({
    name: 'project-planner',
    params: { ...route.params, name: row.name },
  });
}

function onAskDelete(row: SimulatorPlan) {
  planToDelete.value = row;
  confirmDelete.value = true;
}

async function onConfirmDelete() {
  if (!planToDelete.value) return;
  await plansStore.deletePlan(planToDelete.value.id);
  confirmDelete.value = false;
  planToDelete.value = null;
  await refresh();
}

onMounted(refresh);
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
            {{ plansStore.plans.length }}
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
          :loading="creating"
          @click="onStartProject"
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
        :rows="plansStore.plans"
        :loading="plansStore.loading"
        row-key="id"
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
                    @click="onDuplicate(props.row)"
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
                    @click="onEdit(props.row)"
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
                    @click="onAskDelete(props.row)"
                  />
                </div>
              </template>
              <template v-else>{{ col.value }}</template>
            </q-td>
          </q-tr>
        </template>
      </q-table>
    </div>
  </section>

  <q-dialog v-model="confirmDelete" class="modal modal--md" persistent>
    <q-card class="column">
      <q-card-section class="flex justify-between items-center">
        <div class="text-h4 text-weight-medium">
          {{
            $t('common_delete_dialog_title', {
              item: planToDelete?.name ?? '',
            })
          }}
        </div>
        <q-btn
          v-close-popup
          flat
          size="md"
          icon="o_close"
          color="grey-6"
          class="text-weight-medium"
        />
      </q-card-section>
      <q-separator />
      <!-- q-form so Enter submits the dialog (autofocus on the submit button
           gives the native form an Enter target — there are no text inputs). -->
      <q-form @submit.prevent="onConfirmDelete">
        <q-card-section class="q-py-lg q-px-md">
          <span class="text-body1">
            {{
              $t('common_delete_dialog_description', {
                item: planToDelete?.name ?? '',
              })
            }}
          </span>
        </q-card-section>
        <q-separator />
        <q-card-actions class="q-py-lg q-px-md row q-gutter-sm">
          <q-btn
            type="button"
            color="grey-4"
            text-color="primary"
            :label="$t('common_cancel')"
            unelevated
            no-caps
            outline
            size="md"
            class="text-weight-medium col"
            @click="confirmDelete = false"
          />
          <q-btn
            type="submit"
            autofocus
            color="info"
            :label="$t('common_delete')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium col"
          />
        </q-card-actions>
      </q-form>
    </q-card>
  </q-dialog>
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
