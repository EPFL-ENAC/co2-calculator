<template>
  <!-- Rendered by App.vue instead of the router view when APP_DEMO_MODE is
       on. The production app is the prominent action; continuing to the demo
       stays possible (trainings, presentations) but is deliberately
       understated. -->
  <div class="fullscreen bg-grey-1 flex flex-center q-pa-md">
    <div class="col-12 col-md-10 col-lg-8 col-xl-8">
      <q-card
        bordered
        flat
        class="q-px-lg text-center"
        style="padding: 3rem"
        data-testid="demo-instance-notice"
      >
        <div class="column items-center q-gutter-y-xl">
          <div class="column items-center q-gutter-y-md">
            <q-icon :name="outlinedScience" size="lg" color="accent" />
            <div class="text-h4 text-weight-medium text-dark">
              {{ t('demo_instance_title') }}
            </div>
          </div>

          <div class="q-px-lg" style="max-width: 600px">
            <p class="text-body1 text-grey-6 q-ma-none">
              {{ t('demo_instance_message') }}
            </p>
          </div>

          <q-btn
            color="accent"
            :href="runtimeConfig.productionUrl"
            :label="t('demo_instance_button')"
            :icon-right="outlinedOpenInNew"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium q-px-xl"
          />

          <q-btn
            flat
            no-caps
            dense
            size="sm"
            color="grey-7"
            :label="t('demo_instance_continue')"
            data-testid="demo-instance-continue"
            @click="emit('continue')"
          />
        </div>
      </q-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import {
  outlinedOpenInNew,
  outlinedScience,
} from '@quasar/extras/material-icons-outlined';
import { useI18n } from 'vue-i18n';
import { runtimeConfig } from '@/config/runtime';

const emit = defineEmits<{ continue: [] }>();
const { t } = useI18n();
</script>
