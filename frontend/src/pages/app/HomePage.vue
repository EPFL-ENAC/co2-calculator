<script setup lang="ts">
import { MODULES, MODULES_DESCRIPTIONS } from 'src/constant/modules';
</script>

<template>
  <q-page class="layout-grid">
    <q-card flat class="container">
      <h1 class="text-h2 q-mb-md">{{ $t('home_title') }}</h1>
      <p class="text-body1">{{ $t('home_intro_1') }}</p>
      <p class="text-body1">{{ $t('home_intro_2') }}</p>
      <p class="text-body1">{{ $t('home_intro_3') }}</p>
      <p class="text-body1">{{ $t('home_intro_4') }}</p>
      <p class="text-body1">
        <span
          v-html="
            $t('home_intro_5')
              .replace(
                '{documentationLink}',
                $t('info_with_link', {
                  url: '/documentation',
                  linkText: $t('documentation'),
                }),
              )
              .replace(
                '{contactLink}',
                $t('info_with_link', {
                  url: '/contact',
                  linkText: $t('contact'),
                }),
              )
          "
        ></span>
      </p>
      <p class="text-body1 q-mb-none">{{ $t('home_intro_6') }}</p>
      <q-btn
        color="accent"
        :label="$t('home_start_button')"
        unelevated
        no-caps
        size="md"
        class="text-weight-medium q-mt-xl"
      />
    </q-card>

    <div class="column-grid-2">
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
          />
          <div class="column items-end">
            <p class="text-h1 text-weight-medium q-mb-none">42'000</p>
            <p class="text-secondary text-body2 q-mb-none">
              {{ $t('home_results_units') }}
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
      <span class="text-h5 text-weight-medium q-mb-md">{{
        $t('workspace_setup_unit_counter', {
          count: Object.keys(MODULES).length + 1,
        })
      }}</span>
      <div class="column-grid-3">
        <q-card flat class="container">
          <div class="flex justify-between">
            <div class="q-gutter-sm row items-center">
              <q-icon name="o_diversity_2" color="accent" size="sm" />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(MODULES.MyLab) }}
              </h3>
            </div>
            <q-badge rounded color="accent" class="q-pa-sm" label="Validated" />
          </div>
          <p class="text-body2 text-secondary q-mt-md">
            {{ $t(MODULES_DESCRIPTIONS.MyLab) }}
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
            />
            <div class="row q-gutter-xs text-body1 items-baseline">
              <p class="text-weight-medium q-mb-none">8'250</p>
              <p class="text-body2 text-secondary q-mb-none">
                {{ $t('home_results_units') }}
              </p>
            </div>
          </div>
        </q-card>
        <q-card flat class="container">
          <div class="flex justify-between">
            <div class="q-gutter-sm row items-center">
              <q-icon name="o_flight" color="accent" size="sm" />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(MODULES.ProfessionalTravel) }}
              </h3>
            </div>
            <q-badge
              rounded
              color="grey-2"
              text-color="grey-6"
              label="In Progress"
            />
          </div>
          <p class="text-body2 text-secondary q-mt-md">
            {{ $t(MODULES_DESCRIPTIONS.ProfessionalTravel) }}
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
            />
            <div class="row q-gutter-xs text-body1 items-baseline">
              <p class="text-weight-medium q-mb-none">8'250</p>
              <p class="text-body2 text-secondary q-mb-none">
                {{ $t('home_results_units') }}
              </p>
            </div>
          </div>
        </q-card>
        <q-card flat class="container">
          <div class="flex justify-between">
            <div class="q-gutter-sm row items-center">
              <q-icon name="o_domain" color="accent" size="sm" />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(MODULES.Infrastructure) }}
              </h3>
            </div>
          </div>
          <p class="text-body2 text-secondary q-mt-md">
            {{ $t(MODULES_DESCRIPTIONS.Infrastructure) }}
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
            />
            <div class="row q-gutter-xs text-body1 items-baseline">
              <p class="text-weight-medium q-mb-none">8'250</p>
              <p class="text-body2 text-secondary q-mb-none">
                {{ $t('home_results_units') }}
              </p>
            </div>
          </div>
        </q-card>
        <q-card flat class="container">
          <div class="flex justify-between">
            <div class="q-gutter-sm row items-center">
              <q-icon name="o_bolt" color="accent" size="sm" />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(MODULES.EquipmentElectricConsumption) }}
              </h3>
            </div>
            <q-badge
              rounded
              color="grey-2"
              text-color="grey-6"
              label="In Progress"
            />
          </div>
          <p class="text-body2 text-secondary q-mt-md">
            {{ $t(MODULES_DESCRIPTIONS.EquipmentElectricConsumption) }}
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
            />
            <div class="row q-gutter-xs text-body1 items-baseline">
              <p class="text-weight-medium q-mb-none">8'250</p>
              <p class="text-body2 text-secondary q-mb-none">
                {{ $t('home_results_units') }}
              </p>
            </div>
          </div>
        </q-card>
        <q-card flat class="container">
          <div class="flex justify-between">
            <div class="q-gutter-sm row items-center">
              <q-icon name="o_sell" color="accent" size="sm" />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(MODULES.Purchase) }}
              </h3>
            </div>
            <q-badge
              rounded
              color="grey-2"
              text-color="grey-6"
              label="In Progress"
            />
          </div>
          <p class="text-body2 text-secondary q-mt-md">
            {{ $t(MODULES_DESCRIPTIONS.Purchase) }}
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
            />
            <div class="row q-gutter-xs text-body1 items-baseline">
              <p class="text-weight-medium q-mb-none">8'250</p>
              <p class="text-body2 text-secondary q-mb-none">
                {{ $t('home_results_units') }}
              </p>
            </div>
          </div>
        </q-card>
        <q-card flat class="container">
          <div class="flex justify-between">
            <div class="q-gutter-sm row items-center">
              <q-icon name="o_apps" color="accent" size="sm" />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(MODULES.InternalServices) }}
              </h3>
            </div>
            <q-badge
              rounded
              color="grey-2"
              text-color="grey-6"
              label="In Progress"
            />
          </div>
          <p class="text-body2 text-secondary q-mt-md">
            {{ $t(MODULES_DESCRIPTIONS.InternalServices) }}
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
            />
            <div class="row q-gutter-xs text-body1 items-baseline">
              <p class="text-weight-medium q-mb-none">8'250</p>
              <p class="text-body2 text-secondary q-mb-none">
                {{ $t('home_results_units') }}
              </p>
            </div>
          </div>
        </q-card>
        <q-card flat class="container">
          <div class="flex justify-between">
            <div class="q-gutter-sm row items-center">
              <q-icon name="o_filter_drama" color="accent" size="sm" />
              <h3 class="text-h5 text-weight-medium">
                {{ $t(MODULES.ExternalCloud) }}
              </h3>
            </div>
            <q-badge
              rounded
              color="grey-2"
              text-color="grey-6"
              label="In Progress"
            />
          </div>
          <p class="text-body2 text-secondary q-mt-md">
            {{ $t(MODULES_DESCRIPTIONS.ExternalCloud) }}
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
            />
            <div class="row q-gutter-xs text-body1 items-baseline">
              <p class="text-weight-medium q-mb-none">8'250</p>
              <p class="text-body2 text-secondary q-mb-none">
                {{ $t('home_results_units') }}
              </p>
            </div>
          </div>
        </q-card>
      </div>
    </div>
  </q-page>
</template>
