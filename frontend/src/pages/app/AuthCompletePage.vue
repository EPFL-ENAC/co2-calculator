<template>
  <q-page class="fullscreen bg-grey-1 flex flex-center q-pa-md">
    <div class="col-12 col-md-8 col-lg-6 col-xl-5">
      <q-card
        bordered
        flat
        class="q-px-lg text-center"
        style="padding: 3rem"
      >
        <div class="column items-center q-gutter-y-xl">
          <!-- In progress -->
          <template v-if="state === 'progress'">
            <q-icon name="o_lock" size="lg" color="primary" />
            <div class="text-h5 text-weight-medium">
              {{ t('auth_complete_title') }}
            </div>
            <q-spinner color="primary" size="2rem" />
            <p class="text-body1 text-grey-7 q-ma-none">
              {{ t('auth_complete_in_progress') }}
            </p>
          </template>

          <!-- Failure -->
          <template v-else>
            <q-icon name="o_error" size="lg" color="negative" />
            <div class="text-h5 text-weight-medium">
              {{ t('auth_complete_failed') }}
            </div>
            <q-btn
              color="primary"
              :label="t('auth_complete_back_to_login')"
              unelevated
              no-caps
              size="md"
              class="q-px-xl"
              @click="goToLogin"
            />
          </template>
        </div>
      </q-card>
    </div>
  </q-page>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { useAuthStore } from 'src/stores/auth';
import { API_LOGIN_URL } from 'src/api/http';

const router = useRouter();
const { t } = useI18n();
const authStore = useAuthStore();

const state = ref<'progress' | 'failed'>('progress');

function goToLogin() {
  window.location.replace(API_LOGIN_URL);
}

function readCodeFromFragment(): string | null {
  // OAuth callback redirects to /auth/complete#code=<token>; we use the
  // fragment (not the query) so the code never reaches server logs or
  // Referer headers on any third-party asset the SPA pulls.
  const hash = window.location.hash;
  if (!hash || hash.length <= 1) return null;
  const params = new URLSearchParams(hash.slice(1));
  return params.get('code');
}

onMounted(async () => {
  const code = readCodeFromFragment();
  if (!code) {
    state.value = 'failed';
    return;
  }

  try {
    await authStore.exchange(code);
    // Strip the fragment so a refresh doesn't try to redeem an
    // already-consumed code.
    window.history.replaceState(
      null,
      '',
      window.location.pathname + window.location.search,
    );
    // Route to root — the language redirect + workspace-setup guard
    // will steer the user to the right post-login destination.
    await router.replace('/');
  } catch (err: unknown) {
    // Narrow per project convention — `unknown`, not `any`.
    const message = err instanceof Error ? err.message : String(err);
    console.error('Exchange failed', message);
    state.value = 'failed';
  }
});
</script>
