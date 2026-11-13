<template>
  <!-- Rendered by App.vue instead of the router view when a required
       institution value is empty or wrong (#3244): the operator sees which
       values to set instead of an app with blank names and broken links. -->
  <div class="fullscreen bg-grey-1 flex flex-center q-pa-md">
    <div class="col-12 col-md-10 col-lg-8 col-xl-8">
      <q-card
        bordered
        flat
        class="q-px-lg text-center"
        style="padding: 3rem"
        data-testid="missing-config-notice"
      >
        <div class="column items-center q-gutter-y-xl">
          <div class="column items-center q-gutter-y-md">
            <q-icon :name="outlinedSettings" size="lg" color="accent" />
            <div class="text-h4 text-weight-medium text-dark">
              {{ t('missing_config_title') }}
            </div>
          </div>
          <p class="text-body1 text-grey-6 q-ma-none" style="max-width: 600px">
            {{ t('missing_config_message') }}
          </p>
          <ul
            v-if="missingKeys.length > 0"
            class="text-left q-ma-none"
            data-testid="missing-config-keys"
          >
            <li v-for="key in missingKeys" :key="key">
              <code>{{ key }}</code>
            </li>
          </ul>
          <ul
            v-if="invalidKeys.length > 0"
            class="text-left q-ma-none"
            data-testid="invalid-config-keys"
          >
            <li v-for="key in invalidKeys" :key="key">
              <code>{{ key }}</code>
              {{ t('missing_config_trailing_slash') }}
            </li>
          </ul>
        </div>
      </q-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { outlinedSettings } from '@quasar/extras/material-icons-outlined';
import { useI18n } from 'vue-i18n';

defineProps<{
  missingKeys: readonly string[];
  invalidKeys: readonly string[];
}>();
const { t } = useI18n();
</script>
