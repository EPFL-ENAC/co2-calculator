<template>
  <!-- Rendered by App.vue instead of the router view when the session check
       failed and nobody is known yet (#2983): the user is neither signed in
       nor out, so the login page would be the wrong answer. -->
  <div class="fullscreen bg-grey-1 flex flex-center q-pa-md">
    <div class="col-12 col-md-10 col-lg-8 col-xl-8">
      <q-card
        bordered
        flat
        class="q-px-lg text-center"
        style="padding: 3rem"
        data-testid="session-unavailable-notice"
      >
        <div class="column items-center q-gutter-y-xl">
          <div class="column items-center q-gutter-y-md">
            <q-icon :name="outlinedWarning" size="lg" color="accent" />
            <div class="text-h4 text-weight-medium text-dark">
              {{ t('session_unavailable_title') }}
            </div>
          </div>

          <div class="q-px-lg" style="max-width: 600px">
            <p class="text-body1 text-grey-6 q-ma-none">
              {{ t('session_unavailable_message') }}
            </p>
          </div>

          <q-btn
            color="accent"
            :label="t('session_unavailable_retry')"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium q-px-xl"
            data-testid="session-unavailable-retry"
            @click="reload"
          />
        </div>
      </q-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { outlinedWarning } from '@quasar/extras/material-icons-outlined';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

// A full reload re-runs the whole boot, the URL the user asked for included.
function reload() {
  window.location.reload();
}
</script>
