<script setup lang="ts">
import { computed, defineAsyncComponent, h, onMounted, watch } from 'vue';
import { QSkeleton } from 'quasar';
import { useI18n } from 'vue-i18n';
import { MODULES_LIST } from 'src/constant/modules';
import { useWorkspaceStore } from 'src/stores/workspace';
import { useAuthStore } from 'src/stores/auth';
import { useTimelineStore, useModuleStore } from 'src/stores/modules';
import { useYearConfigStore } from 'src/stores/yearConfig';
import { nOrDash } from 'src/utils/number';
import WorkspaceSelectorBar from 'src/components/organisms/workspace-selector/WorkspaceSelectorBar.vue';
import CO2ProjectPlanner from 'src/components/organisms/home/CO2ProjectPlanner.vue';
import CO2Explorer from 'src/components/organisms/home/CO2Explorer.vue';

const workspaceStore = useWorkspaceStore();
const authStore = useAuthStore();
const moduleStore = useModuleStore();
const timelineStore = useTimelineStore();
const yearConfigStore = useYearConfigStore();
const { t, te, locale, getLocaleMessage } = useI18n();

/** A translation key resolves to displayable content (exists and non-empty). */
const hasText = (key: string) => te(key) && t(key).trim().length > 0;

/** Keeps the ECharts-heavy bundle out of the initial home route chunk. */
const ChartSkeleton = () =>
  h(QSkeleton, { type: 'rect', height: '360px', class: 'full-width' });

const ModuleCarbonFootprintChart = defineAsyncComponent({
  loader: () =>
    import('src/components/charts/results/ModuleCarbonFootprintChart.vue'),
  loadingComponent: ChartSkeleton,
  delay: 0,
});

const currentYear = computed(
  () => workspaceStore.selectedYear ?? new Date().getFullYear(),
);

const validatedTotals = computed(() => {
  const carbonReportId = timelineStore.currentCarbonReportId;
  if (
    carbonReportId &&
    carbonReportId !== moduleStore.validatedTotalsCarbonReportId
  ) {
    moduleStore.getValidatedTotals(carbonReportId);
  }
  return moduleStore.state.validatedTotals;
});

// The headline figure is shown in tonnes CO₂-eq with one decimal.
const totalTonnesCo2 = computed(() =>
  nOrDash(validatedTotals.value?.total_tonnes_co2eq, {
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

// Principal (unit-breadth) users can validate module status; standard (own)
// users cannot. We use the same signal to tailor the empty-state access copy.
const isPrincipalUser = computed(() =>
  authStore.hasUserCanValidateModuleStatus(),
);

// Drives the role-scoped i18n keys (co2_calculator_role_*, _access_*_title/_body).
const userType = computed(() =>
  isPrincipalUser.value ? 'principal' : 'standard',
);

// EPFL access-management portal, opened straight on the authorizations tab.
// Principals delegate roles here; standard users instead email the principal.
const ACCRED_URL = 'https://accred.epfl.ch?opentab=authorizations';

const principalUserName = computed(
  () => workspaceStore.selectedUnit?.principal_user_name ?? '',
);

// Standard users request access by emailing the unit's principal user, with a
// pre-filled subject/body. Null when no principal email is known for the unit.
const requestAccessMailto = computed(() => {
  const email = workspaceStore.selectedUnit?.principal_user_email;
  if (!email) return null;
  const unit = workspaceStore.selectedUnit?.name ?? '';
  const subject = t('co2_calculator_access_mail_subject', { unit });
  const body = t('co2_calculator_access_mail_body', {
    name: principalUserName.value,
    unit,
  });
  return `mailto:${email}?subject=${encodeURIComponent(
    subject,
  )}&body=${encodeURIComponent(body)}`;
});

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

  return indices
    .map((i) => ({
      title: `calculator_update_${i}_title`,
      date: `calculator_update_${i}_date`,
      body: `calculator_update_${i}_body`,
    }))
    // Drop entries with no content; their leading separator goes with them.
    .filter((update) => hasText(update.date) || hasText(update.body));
});

async function fetchEmissionBreakdown() {
  const carbonReportId = workspaceStore.selectedCarbonReport?.id;
  if (!carbonReportId) return;
  await moduleStore.getEmissionBreakdown(carbonReportId, []);
}

onMounted(fetchEmissionBreakdown);

watch(
  () => workspaceStore.selectedCarbonReport?.id,
  async () => {
    moduleStore.invalidateEmissionBreakdown();
    await fetchEmissionBreakdown();
  },
);
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
            type="a"
            target="_blank"
            rel="noopener noreferrer"
            color="grey-4"
            text-color="primary"
            :label="$t('co2_calculator_about')"
            icon="o_info"
            unelevated
            no-caps
            outline
            size="sm"
            class="text-weight-medium"
          />
        </div>

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

              <!-- Discreet role badge; opens a popover explaining the access
                   level and how to request more (ACCRED). Always available,
                   independent of the empty/populated chart state. -->
              <q-btn
                flat
                dense
                no-caps
                size="sm"
                class="calculator-card__role-chip"
                :class="{
                  'calculator-card__role-chip--principal': isPrincipalUser,
                }"
              >
                <q-icon
                  :name="isPrincipalUser ? 'o_verified_user' : 'o_lock'"
                  size="xs"
                  class="q-mr-xs"
                />
                {{ $t(`co2_calculator_role_${userType}`) }}
                <q-icon name="expand_more" size="xs" class="q-ml-xs" />
                <q-menu anchor="bottom right" self="top right" :offset="[0, 6]">
                  <div class="calculator-card__access-popover">
                    <p class="text-subtitle2 text-weight-medium q-mb-xs">
                      {{ $t(`co2_calculator_access_${userType}_title`) }}
                    </p>
                    <p class="text-body2 text-secondary q-mb-md">
                      {{ $t(`co2_calculator_access_${userType}_body`) }}
                    </p>

                    <!-- Principals delegate roles in ACCRED. -->
                    <a
                      v-if="isPrincipalUser"
                      :href="ACCRED_URL"
                      target="_blank"
                      rel="noopener noreferrer"
                      class="link text-body2 text-weight-medium"
                    >
                      {{ $t('co2_calculator_access_cta_principal') }}
                      <q-icon name="o_arrow_outward" size="xs" />
                    </a>

                    <!-- Standard users email their unit's principal user. -->
                    <q-btn
                      v-else-if="requestAccessMailto"
                      type="a"
                      :href="requestAccessMailto"
                      color="info"
                      icon="o_mail"
                      :label="$t('co2_calculator_access_cta_standard')"
                      unelevated
                      no-caps
                      size="sm"
                      class="text-weight-medium"
                    />
                    <p v-else class="text-body2 text-secondary q-mb-none">
                      {{
                        $t('co2_calculator_access_no_email', {
                          name: principalUserName,
                        })
                      }}
                    </p>
                  </div>
                </q-menu>
              </q-btn>
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
@use 'src/css/02-tokens' as tokens;

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

// Discreet role badge in the card header. Neutral pill, color keyed to role,
// opens the access popover below.
.calculator-card__role-chip {
  color: tokens.$color-text;
  border: 1px solid tokens.$color-text;
  border-radius: tokens.$radius-pill;
  padding: 2px tokens.$spacing-sm;
  flex-shrink: 0;

  &--principal {
    color: tokens.$color-validated;
    border-color: tokens.$color-validated;
  }
}

// Access details revealed from the role badge.
.calculator-card__access-popover {
  max-width: 400px;
  padding: tokens.$spacing-xl;
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
