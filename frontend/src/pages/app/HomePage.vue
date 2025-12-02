<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { MODULES } from 'src/constant/modules';
import { MODULE_CARDS } from 'src/constant/moduleCards';

const { t } = useI18n();

const modulesCounterText = computed(() =>
  t('home_modules_counter', {
    count: Object.keys(MODULES).length + 1,
  }),
);

const homeIntroWithLinks = computed(() => {
  return t('home_intro_5')
    .replace(
      '{documentationLink}',
      t('info_with_link', {
        url: '/documentation',
        linkText: t('documentation'),
      }),
    )
    .replace(
      '{contactLink}',
      t('info_with_link', {
        url: '/contact',
        linkText: t('contact'),
      }),
    );
});
</script>

<template>
  <q-page class="page-grid">
    <q-card flat class="container">
      <h1 class="text-h2 q-mb-md">{{ $t('home_title') }}</h1>
      <p class="text-body1">{{ $t('home_intro_1') }}</p>
      <p class="text-body1">{{ $t('home_intro_2') }}</p>
      <p class="text-body1">{{ $t('home_intro_3') }}</p>
      <p class="text-body1">{{ $t('home_intro_4') }}</p>
      <p class="text-body1">
        <span>
          {{ homeIntroWithLinks }}
        </span>
      </p>
      <p class="text-body1 q-mb-none">{{ $t('home_intro_6') }}</p>
      <q-btn
        color="accent"
        :label="$t('home_start_button')"
        unelevated
        no-caps
        size="md"
        class="text-weight-medium q-mt-xl"
        :to="{ name: 'module', params: { module: MODULES.MyLab } }"
      />
    </q-card>

    <div class="grid-2-col">
      <q-card flat class="container">
        <h3 class="text-h4 text-weight-medium">
          {{ $t('home_results_title') }}
        </h3>
        <h3 class="text-h5 text-weight-medium text-secondary">
          {{ $t('home_results_subtitle') }}
        </h3>
        <div class="flex justify-between items-end q-mt-xl">
          <q-btn
            color="accent"
            :label="$t('home_results_btn')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium"
            :to="{ name: 'results' }"
          />
          <div class="column items-end">
            <p class="text-h1 text-weight-medium q-mb-none">42'000</p>
            <p class="text-secondary text-body2 q-mb-none">
              {{ $t('results_units') }}
            </p>
          </div>
        </div>
      </q-card>
      <q-card flat class="container">
        <h3 class="text-h4 text-weight-medium">
          {{ $t('home_simulations_title') }}
        </h3>
        <h3 class="text-h5 text-weight-medium text-secondary">
          {{ $t('home_simulations_subtitle') }}
        </h3>
        <div class="flex justify-between items-end q-mt-xl">
          <q-btn
            color="accent"
            :label="$t('home_simulations_btn')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium"
            :to="{ name: 'simulations' }"
          />
          <div class="column items-end">
            <p class="text-h1 text-weight-medium q-mb-none">3</p>
            <p class="text-secondary text-body2 q-mb-none">
              {{ $t('home_simulations_units') }}
            </p>
          </div>
        </div>
      </q-card>
    </div>

    <div>
      <div class="text-h5 text-weight-medium q-mb-sm">
        {{ modulesCounterText }}
      </div>
      <div class="grid-3-col">
        <q-card
          v-for="moduleCard in MODULE_CARDS"
          :key="moduleCard.module"
          flat
          class="container"
        >
          <div class="flex justify-between">
            <div class="q-gutter-sm row items-center">
              <q-icon :name="moduleCard.icon" color="accent" size="sm" />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(moduleCard.module) }}
              </h3>
            </div>
            <q-badge
              v-if="moduleCard.badge"
              rounded
              :color="moduleCard.badge.color"
              :text-color="moduleCard.badge.textColor"
              :class="moduleCard.badge.color === 'accent' ? 'q-pa-sm' : ''"
              :label="
                moduleCard.badge.label.startsWith('home_')
                  ? $t(moduleCard.badge.label)
                  : moduleCard.badge.label
              "
            />
          </div>
          <p class="text-body2 text-secondary q-mt-md">
            {{ $t(`${moduleCard.module}-description`) }}
          </p>
          <q-separator class="grey-6 q-my-lg" />
          <div class="flex justify-between items-center">
            <q-btn
              icon="o_edit"
              :label="$t('home_edit_btn')"
              unelevated
              no-caps
              size="sm"
              class="text-weight-medium btn-secondary"
              :to="{ name: 'module', params: { module: moduleCard.module } }"
            />
            <div
              v-if="moduleCard.value"
              class="row q-gutter-xs text-body1 items-baseline"
            >
              <p class="text-weight-medium q-mb-none">{{ moduleCard.value }}</p>
              <p class="text-body2 text-secondary q-mb-none">
                {{ $t('results_units') }}
              </p>
            </div>
          </div>
        </q-card>
      </div>
    </div>
  </q-page>
</template>
