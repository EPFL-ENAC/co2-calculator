<script setup lang="ts">
import { computed, defineAsyncComponent, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { MODULES_LIST } from '@/constant/modules';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';
import { useModuleStore } from '@/stores/modules';
import { useYearConfigStore } from '@/stores/yearConfig';
import { nOrDash } from '@/utils/number';
import WorkspaceSelectorBar from '@/components/organisms/workspace-selector/WorkspaceSelectorBar.vue';
import CO2ProjectPlanner from '@/components/organisms/home/CO2ProjectPlanner.vue';
import CO2Explorer from '@/components/organisms/home/CO2Explorer.vue';
import ChartSkeleton from '@/components/charts/ChartSkeleton.vue';

const workspaceStore = useWorkspaceStore();
const authStore = useAuthStore();
const moduleStore = useModuleStore();
const yearConfigStore = useYearConfigStore();
const { t, te, locale, getLocaleMessage } = useI18n();

/** A translation key resolves to displayable content (exists and non-empty). */
const hasText = (key: string) => te(key) && t(key).trim().length > 0;

// Lazy-loaded so the ECharts-heavy bundle stays out of the initial home route
// chunk; ChartSkeleton holds the layout while it loads.
const ModuleCarbonFootprintChart = defineAsyncComponent({
  loader: () =>
    import('@/components/charts/results/ModuleCarbonFootprintChart.vue'),
  loadingComponent: ChartSkeleton,
  delay: 0,
});

const currentYear = computed(
  () => workspaceStore.selectedYear ?? new Date().getFullYear(),
);

// The headline figure is shown in tonnes CO₂-eq with one decimal. The
// validated-only total rides inside the emission breakdown hydrated by the
// workspace guard's single aggregate call — no fetch on mount.
const totalTonnesCo2 = computed(() =>
  nOrDash(moduleStore.state.emissionBreakdown?.total_tonnes_validated_co2eq, {
    options: { minimumFractionDigits: 1, maximumFractionDigits: 1 },
  }),
);

/**
 * The chart only carries meaning once a module has been validated. Until then
 * we show the empty "ready to start" state instead of an empty chart.
 */
const hasValidatedData = computed(
  () =>
    (moduleStore.state.emissionBreakdown?.validated_categories?.length ?? 0) >
    0,
);

const firstEditableModule = computed(() =>
  MODULES_LIST.find(
    (module) =>
      yearConfigStore.isModuleVisible(module) &&
      authStore.canUserAccessModule(module),
  ),
);

const isAboutDialogOpen = ref(false);

const calculatorUpdates = computed(() => {
  // Discover update indices from the i18n keys (calculator_update_<n>_*) instead
  // of hard-coding a count, so adding entries only requires editing the locale file.
  const indices = [
    ...new Set(
      Object.keys(getLocaleMessage(locale.value))
        .map((key) => key.match(/^calculator_update_(\d+)_/)?.[1])
        .filter((n): n is string => n != null),
    ),
  ].sort((a, b) => Number(a) - Number(b));

  return (
    indices
      .map((i) => ({
        title: `calculator_update_${i}_title`,
        date: `calculator_update_${i}_date`,
        body: `calculator_update_${i}_body`,
      }))
      // Drop entries with no content; their leading separator goes with them.
      .filter((update) => hasText(update.date) || hasText(update.body))
  );
});
</script>

<template>
  <q-page>
    <div class="home-workspace-bar">
      <div class="home-workspace-bar__inner">
        <WorkspaceSelectorBar />
      </div>
    </div>

    <div class="page-grid">
      <!-- CO₂ Calculator — title/text/actions sit on the page (no card),
           only the chart + updates panel is bordered. -->
      <section class="co2-calculator">
        <div class="row items-start justify-between no-wrap q-mb-md">
          <div class="row items-center q-gutter-sm">
            <q-icon name="o_calculate" size="md" color="info" />
            <h1 class="text-h2 q-mb-none">{{ $t('co2_calculator_title') }}</h1>
          </div>
          <q-btn
            color="info"
            :label="$t('co2_calculator_about')"
            icon="o_info"
            unelevated
            no-caps
            outline
            dense
            size="sm"
            padding="4px 10px 4px 8px"
            class="text-weight-medium about-btn"
            @click="isAboutDialogOpen = true"
          />
        </div>

        <q-dialog v-model="isAboutDialogOpen">
          <q-card class="about-dialog">
            <q-card-section
              class="row items-center no-wrap about-dialog__header"
            >
              <q-icon name="o_info" size="xs" color="info" class="q-mr-sm" />
              <span class="text-subtitle1 text-weight-medium col">
                {{ $t('co2_calculator_about') }}
              </span>
              <q-btn
                v-close-popup
                flat
                round
                dense
                size="sm"
                icon="o_close"
                color="grey-7"
              />
            </q-card-section>
            <q-separator />
            <q-card-section class="about-dialog__body">
              <div class="about-dialog__item">
                <div class="about-dialog__icon">
                  <q-icon
                    name="o_arrow_circle_right"
                    size="22px"
                    color="info"
                  />
                </div>
                <p class="text-body2 text-grey-9 q-mb-none">
                  {{ $t('co2_calculator_about_paragraph_1') }}
                </p>
              </div>
              <div class="about-dialog__item">
                <div class="about-dialog__icon">
                  <q-icon name="o_upload_file" size="24px" color="info" />
                </div>
                <p class="text-body2 text-grey-9 q-mb-none">
                  {{ $t('co2_calculator_about_paragraph_2') }}
                </p>
              </div>
              <div class="about-dialog__item">
                <div class="about-dialog__icon">
                  <q-icon name="o_visibility" size="24px" color="info" />
                </div>
                <p class="text-body2 text-grey-9 q-mb-none">
                  {{ $t('co2_calculator_about_paragraph_3') }}
                </p>
              </div>
            </q-card-section>
          </q-card>
        </q-dialog>

        <p class="text-body1 section-intro">
          {{ $t('home_intro_1_part_1')
          }}<a
            :href="$t('home_intro_1_link_url')"
            target="_blank"
            rel="noopener noreferrer"
            class="link"
            >{{ $t('home_intro_1_link_text') }}</a
          >{{ $t('home_intro_1_part_2') }}
        </p>
        <p class="text-body1 section-intro">
          {{ $t('home_intro_4_part_1')
          }}<a
            :href="$t('home_intro_4_link_url')"
            target="_blank"
            rel="noopener noreferrer"
            class="link"
            >{{ $t('home_intro_4_link_text') }}</a
          >{{ $t('home_intro_4_part_2')
          }}<a :href="$t('home_intro_4_contact_link_url')" class="link">{{
            $t('home_intro_4_contact_link_text')
          }}</a
          >{{ $t('home_intro_4_part_3') }}
        </p>

        <!-- Calculator card: two full-height columns separated by a vertical
             divider. Left = title · chart · actions/total; right = updates. -->
        <q-card flat bordered class="q-mt-xl calculator-card">
          <!-- Left column: title, chart, then actions + total footer -->
          <div class="calculator-card__main">
            <div
              class="calculator-card__header row items-center justify-between no-wrap"
            >
              <h2 class="text-h5 text-weight-medium q-mb-none">
                {{ $t('co2_calculator_chart_title', { year: currentYear }) }}
              </h2>
            </div>

            <q-separator />

            <div class="calculator-card__chart">
              <ModuleCarbonFootprintChart
                v-if="hasValidatedData"
                :breakdown-data="moduleStore.state.emissionBreakdown"
                :bordered="false"
                hide-header
                hide-actions
                module-icon-axis
              />
              <div v-else class="calculator-card__empty">
                <q-icon name="o_bar_chart" size="48px" color="info" />
                <h3 class="text-h5 text-weight-medium q-mt-md q-mb-sm">
                  {{ $t('co2_calculator_empty_title') }}
                </h3>
                <p class="text-body2 text-secondary q-mb-lg">
                  {{
                    $t('co2_calculator_empty_subtitle', { year: currentYear })
                  }}
                </p>
                <q-btn
                  color="info"
                  :label="$t('co2_calculator_empty_btn')"
                  icon-right="o_arrow_circle_right"
                  unelevated
                  no-caps
                  size="md"
                  class="text-weight-medium"
                  :to="{
                    name: 'module',
                    params: { module: firstEditableModule },
                  }"
                  :disable="!firstEditableModule"
                />
              </div>
            </div>

            <q-separator />

            <div class="calculator-card__footer">
              <div v-if="hasValidatedData" class="row items-center q-gutter-sm">
                <q-btn
                  color="info"
                  :label="$t('co2_calculator_continue')"
                  icon-right="o_arrow_circle_right"
                  unelevated
                  no-caps
                  size="md"
                  class="text-weight-medium"
                  :to="{
                    name: 'module',
                    params: { module: firstEditableModule },
                  }"
                  :disable="!firstEditableModule"
                />
                <q-btn
                  color="grey-4"
                  text-color="primary"
                  :label="$t('home_results_btn')"
                  icon="o_bar_chart"
                  unelevated
                  no-caps
                  outline
                  size="md"
                  class="text-weight-medium"
                  :to="{ name: 'results' }"
                />
              </div>
              <div class="column items-end calculator-card__total">
                <p class="text-h3 text-weight-medium q-mb-none">
                  {{ hasValidatedData ? totalTonnesCo2 : '-' }}
                </p>
                <p class="text-secondary text-caption q-mb-none">
                  {{ $t('results_units_tonnes') }}
                </p>
              </div>
            </div>
          </div>

          <q-separator vertical class="calculator-card__divider" />

          <!-- Right column: calculator updates -->
          <div class="calculator-card__aside">
            <div class="calculator-card__header calculator-card__header--side">
              <q-icon name="o_notifications" size="sm" color="info" />
              <h3 class="text-h5 text-weight-medium q-mb-none">
                {{ $t('calculator_update_title') }}
              </h3>
            </div>

            <div class="calculator-card__updates">
              <template
                v-for="(update, index) in calculatorUpdates"
                :key="update.title"
              >
                <q-separator
                  v-if="index > 0"
                  class="calculator-card__update-separator"
                />
                <div>
                  <div class="row items-center justify-between q-mb-xs no-wrap">
                    <h4 class="text-h6 text-weight-medium q-mb-none">
                      {{ $t(update.title) }}
                    </h4>
                    <span
                      v-if="hasText(update.date)"
                      class="text-caption text-secondary q-ml-md"
                    >
                      {{ $t(update.date) }}
                    </span>
                  </div>
                  <p
                    v-if="hasText(update.body)"
                    class="text-body2 text-secondary q-mb-none"
                  >
                    {{ $t(update.body) }}
                  </p>
                </div>
              </template>
            </div>
          </div>
        </q-card>
      </section>
    </div>

    <!-- Full-width grey band, breaks out of the centred page-grid. -->
    <CO2ProjectPlanner />

    <div class="page-grid">
      <CO2Explorer />
    </div>
  </q-page>
</template>

<style scoped lang="scss">
@use '@/css/02-tokens' as tokens;

.about-btn :deep(.q-icon.on-left) {
  margin-right: tokens.$spacing-sm;
  font-size: 1.25em;
}

.about-dialog {
  width: 100%;
  max-width: 520px;
  border-radius: tokens.$radius-default;
}

.about-dialog__header {
  padding: tokens.$spacing-md tokens.$spacing-md tokens.$spacing-md
    tokens.$spacing-xl;
}

.about-dialog__body {
  display: grid;
  grid-template-columns: tokens.$spacing-xl 1fr;
  column-gap: tokens.$spacing-xl;
  row-gap: tokens.$spacing-xl;
  padding: tokens.$spacing-xxl;
}

.about-dialog__item {
  display: contents;

  p {
    font-size: tokens.$text-size-sm;
    line-height: tokens.$text-line-height-lg;
  }
}

.about-dialog__icon {
  display: flex;
  align-self: start;
  align-items: center;
  justify-content: center;
  width: tokens.$spacing-xl;
  height: tokens.$spacing-xl;
}

// Full-width band pinned under the header; its content is constrained to the
// same centered container width as the page-grid sections below.
.home-workspace-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  width: 100%;
  background-color: tokens.$container-default-bg;
  border-bottom: tokens.$container-border-weight solid
    tokens.$container-default-border;

  &__inner {
    width: 100%;
    max-width: tokens.$layout-page-width;
    margin: 0 auto;
    padding: tokens.$spacing-md tokens.$layout-page-padding-x;
  }
}

// Intro/description text under a section title is capped at three-quarters width.
.section-intro {
  max-width: 75%;
}

// Two-column card: left column (title · chart · footer) and right column
// (updates) stacked on mobile, side-by-side with a full-height divider on wide.
.calculator-card {
  display: flex;
  flex-direction: column;
}

.calculator-card__main,
.calculator-card__aside {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

// Section title bar at the top of each column.
.calculator-card__header {
  padding: tokens.$spacing-xl;
}

.calculator-card__header--side {
  display: flex;
  align-items: center;
  gap: tokens.$spacing-sm;
}

.calculator-card__chart {
  flex: 1;
  padding: tokens.$spacing-lg tokens.$spacing-xl;
}

// Empty "ready to start" state shown in the chart slot before any module is
// validated; fills the same vertical space the chart would occupy.
.calculator-card__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  min-height: 360px;
  height: 100%;
}

.calculator-card__updates {
  padding: tokens.$spacing-xl;
}

// Thin divider between consecutive update entries (not before the first).
.calculator-card__update-separator {
  margin: tokens.$spacing-xl 0;
}

// Total stays pinned to the right even when the action buttons are hidden
// (empty state), where it would otherwise be the footer's only child.
.calculator-card__total {
  margin-left: auto;
}

// Footer lives only inside the left column, beneath the chart.
.calculator-card__footer {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: tokens.$spacing-lg;
  padding: tokens.$spacing-xl;
}

// Vertical divider hidden when columns are stacked.
.calculator-card__divider {
  display: none;
}

@media (min-width: tokens.$breakpoint-desktop-min) {
  .calculator-card {
    flex-direction: row;
    align-items: stretch;
  }

  // Match the 2:1 split between chart and updates columns.
  .calculator-card__main {
    flex: 2;
  }

  .calculator-card__aside {
    flex: 1;
  }

  .calculator-card__footer {
    flex-direction: row;
    align-items: center;
    justify-content: space-between;
  }

  .calculator-card__divider {
    display: block;
    align-self: stretch;
  }
}
</style>
