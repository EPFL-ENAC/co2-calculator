<script setup lang="ts">
import { MODULE_CARDS } from 'src/constant/moduleCards';
import { SYSTEM_NAV } from 'src/constant/sidebarNavigation';
</script>

<template>
  <q-page class="">
    <div class="q-my-xl q-px-xl">
      <div class="flex items-center q-gutter-md">
        <q-icon name="o_view_module" size="sm" color="accent" />
        <span class="text-h3 text-weight-bold">
          {{ $t(SYSTEM_NAV.SYSTEM_MODULE_MANAGEMENT.routeName) }}
        </span>
      </div>
      <span class="text-body1 text-secondary">
        {{ $t(SYSTEM_NAV.SYSTEM_MODULE_MANAGEMENT.description) }}
      </span>
    </div>
    <q-separator />

    <div class="q-my-xl q-px-xl q-pa-none">
      <div class="q-mb-xl">
        <div class="container full-width container--pa-none">
          <div class="flex items-center q-gutter-md">
            <div
              class="bg-accent q-px-md q-mr-xl self-stretch flex items-center"
            >
              <q-icon name="o_warning" size="xs" color="white" />
            </div>
            <div>
              <div class="q-my-xl text-body2">
                <p class="q-mb-none">
                  {{ $t('module_management_consequences_title') }}
                </p>
                <ul class="q-ml-lg">
                  <li>{{ $t('module_management_consequence_no_access') }}</li>
                  <li>{{ $t('module_management_consequence_not_on_home') }}</li>
                  <li>
                    {{ $t('module_management_consequence_not_in_results') }}
                  </li>
                  <li>
                    {{ $t('module_management_consequence_important') }}
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div
        v-for="moduleCard in MODULE_CARDS"
        :key="moduleCard.module"
        class="q-mb-md"
      >
        <div q-card class="container full-width q-mx-lg">
          <div class="flex row justify-between items-center">
            <div>
              <div class="flex items-center q-mb-xs">
                <q-icon
                  :name="moduleCard.icon"
                  size="xs"
                  class="q-mr-sm"
                  color="accent"
                />
                <span class="text-h4 text-weight-medium q-mb-none">
                  {{ $t(moduleCard.module) }}
                </span>
              </div>

              <span class="text-body2 text-secondary">
                {{ $t(`${moduleCard.module}-description`) }}
              </span>
            </div>
            <div>
              <q-checkbox
                v-model="moduleCard.active"
                keep-color
                :label="$t('module_management_active')"
                color="accent"
                class="text-weight-medium"
              />
            </div>
          </div>
        </div>
      </div>

      <q-btn
        color="accent"
        :label="$t('module_management_save_button')"
        unelevated
        no-caps
        size="md"
        class="text-weight-medium"
      />
    </div>
  </q-page>
</template>
