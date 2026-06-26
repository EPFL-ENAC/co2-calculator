<template>
  <div class="fullscreen bg-grey-1 flex flex-center q-pa-md">
    <div class="col-12 col-md-10 col-lg-8 col-xl-8">
      <q-card
        bordered
        flat
        class="q-px-lg text-center"
        style="padding: 3rem"
        padding-top="1rem"
      >
        <div class="column items-center q-gutter-y-xl">
          <!-- Error Code and Icon -->
          <div class="column items-center q-gutter-y-md">
            <q-icon name="o_search_off" size="lg" color="accent" />
            <div class="text-h4 text-weight-medium text-dark">
              {{ t('not_found_title') }}
            </div>
          </div>

          <div class="q-px-lg" style="max-width: 600px">
            <p class="text-body1 text-grey-6 q-ma-none">
              {{ t('not_found_message') }}
            </p>
          </div>

          <div>
            <q-btn
              color="accent"
              :to="homeRoute"
              :label="t('home')"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium q-px-xl"
            />
          </div>

          <div class="q-px-lg" style="max-width: 600px">
            <div class="row items-center q-gutter-x-sm justify-center">
              <p class="text-caption text-grey-7 q-ma-none">
                {{ t('contact') }}: {{ t('not_found_contact_message') }}
              </p>
            </div>
          </div>
        </div>
      </q-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { HOME_ROUTE_NAME, DEFAULT_ROUTE_NAME } from 'src/router/routes';
import { i18n } from 'src/boot/i18n';
import { useWorkspaceStore } from 'src/stores/workspace';

const { t } = useI18n();
const workspaceStore = useWorkspaceStore();

const homeRoute = computed(() => {
  const currentLocale = i18n.global.locale.value;
  const language = currentLocale.split('-')[0] || 'en';

  // Go straight to the workspace home when a unit/year is selected;
  // otherwise fall back to the landing resolver so the required params exist.
  const params = workspaceStore.selectedParams;
  if (params) {
    return {
      name: HOME_ROUTE_NAME,
      params: {
        language,
        unit: encodeURIComponent(params.unit),
        year: params.year,
      },
    };
  }

  return {
    name: DEFAULT_ROUTE_NAME,
    params: { language },
  };
});
</script>
