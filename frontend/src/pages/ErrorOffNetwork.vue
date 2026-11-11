<template>
  <!-- Same background and card header as the login page: the user lands
       here instead of on the login page. -->
  <div class="off-network-page fullscreen flex flex-center q-pa-md">
    <q-card class="off-network-card" data-testid="off-network-card">
      <div class="column q-gutter-y-xl">
        <div class="column items-center q-gutter-y-sm">
          <q-img :src="epflLogo" :alt="t('login_logo_alt')" width="125px" />
          <h2 class="text-weight-medium q-ma-none">{{ t('login_title') }}</h2>
        </div>

        <div class="off-network-message text-center">
          <p class="text-body1 text-weight-medium text-dark q-mt-none q-mb-sm">
            {{ t('off_network_title') }}
          </p>
          <p class="text-body2 text-grey-7 q-ma-none">
            {{ t('off_network_message') }}
          </p>
        </div>

        <div class="column q-gutter-y-sm">
          <q-btn
            color="accent"
            :to="retryRoute"
            :label="t('off_network_retry')"
            unelevated
            no-caps
            size="md"
            class="full-width text-weight-medium"
          />
          <q-btn
            color="accent"
            :href="t('off_network_vpn_url')"
            target="_blank"
            rel="noopener noreferrer"
            :label="t('off_network_vpn_button')"
            outline
            no-caps
            size="md"
            class="full-width text-weight-medium"
          />
        </div>

        <q-separator />

        <p class="text-caption text-grey-7 q-mt-md q-mb-none">
          {{ t('off_network_external_message') }}
          <a :href="contactHref" class="text-accent">{{ contactEmail }}</a>
        </p>
      </div>
    </q-card>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import epflLogo from '@/assets/epfl-logo.svg';
import { useI18n } from 'vue-i18n';
import { DEFAULT_ROUTE_NAME } from '@/router/routes';
import { currentLanguage } from '@/utils/language';

const { t } = useI18n();

const contactEmail = computed(() => t('off_network_contact_email'));
const contactHref = computed(() => `mailto:${contactEmail.value}`);

// Mock for #3196: no real network probe yet. "Retry" re-enters the app,
// which is what the real page will do once the probe passes.
const retryRoute = computed(() => ({
  name: DEFAULT_ROUTE_NAME,
  params: { language: currentLanguage() },
}));
</script>

<style scoped lang="scss">
@use '@/css/02-tokens' as tokens;

// Same background as LoginPage.vue.
.off-network-page {
  &::before {
    content: '';
    position: absolute;
    inset: 0;
    background-image: url('../assets/login-img.svg');
    background-repeat: repeat;
    filter: blur(tokens.$login-page-bg-blur);
    z-index: tokens.$login-page-bg-z-index;
  }

  &::after {
    content: '';
    position: absolute;
    inset: 0;
    background-color: rgba(
      tokens.$login-page-bg-color,
      tokens.$login-page-bg-opacity
    );
    z-index: tokens.$login-page-bg-blur-z-index;
  }
}

// Balanced wrapping avoids a lone word on the last line of each sentence.
.off-network-message p {
  text-wrap: balance;
}

.off-network-card {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 440px;
  padding: tokens.$spacing-page;
  box-shadow: tokens.$login-card-box-shadow;
}
</style>
