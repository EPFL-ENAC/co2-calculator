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
            <q-icon name="o_lock" size="lg" color="accent" />
            <div class="text-h4 text-weight-medium text-dark">
              {{ t('unauthorized_title') }}
            </div>
          </div>

          <!-- Highlighted reason message: a known redirect reason (e.g. the
               account is not assigned to a unit) takes precedence over the
               generic missing-permission hint. -->
          <div
            v-if="highlightMessage"
            class="q-pa-md rounded-borders bg-orange-1"
            style="max-width: 100%"
          >
            <div class="row items-center q-gutter-x-sm justify-center">
              <q-icon name="o_info" size="sm" color="orange-8" />
              <p class="text-body1 text-weight-medium text-orange-9 q-ma-none">
                {{ highlightMessage }}
              </p>
            </div>
          </div>

          <div class="q-px-lg" style="max-width: 600px">
            <p class="text-body1 text-grey-6 q-ma-none">
              {{ t('unauthorized_message') }}
            </p>
          </div>

          <div class="row q-gutter-x-md justify-center">
            <!-- Back-office users always have a legitimate destination there
                 (it's where units are assigned and years are opened), whatever
                 brought them to this page. Same gate + target as the header's
                 back-office button. -->
            <q-btn
              v-if="hasBackOfficeAccess"
              color="accent"
              :to="backOfficeRoute"
              :label="t('user_management_access_button')"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium q-px-xl"
            />
            <!-- A user with no unit or no open year is bounced back to
                 /unauthorized by the landing guard, so "Home" would loop:
                 hide it for those dead-end reasons. -->
            <q-btn
              v-if="!isDeadEndReason"
              color="accent"
              :to="homeRoute"
              :label="t('home')"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium q-px-xl"
              :outline="hasBackOfficeAccess"
            />
            <!-- This fullscreen page has no header, and a broken session
                 (e.g. a stale account after a DB reset) can 403 every call —
                 including "Home" — so Logout must always be reachable here. -->
            <q-btn
              color="accent"
              :label="t('logout')"
              :loading="authStore.loading"
              unelevated
              no-caps
              size="md"
              class="text-weight-medium q-px-xl"
              :outline="hasBackOfficeAccess || !isDeadEndReason"
              @click="onLogout"
            />
          </div>

          <div class="q-px-lg" style="max-width: 600px">
            <div class="row items-center q-gutter-x-sm justify-center">
              <p class="text-caption text-grey-7 q-ma-none">
                {{ t('contact') }}: {{ t('unauthorized_contact_message') }}
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
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { DEFAULT_ROUTE_NAME } from 'src/router/routes';
import { currentLanguage, resolveLanguage } from 'src/utils/language';
import { unauthorizedReasonMessageKey } from 'src/utils/unauthorized';
import { useAuthStore, PermissionAction } from 'src/stores/auth';

const route = useRoute();
const router = useRouter();
const { t } = useI18n();
const authStore = useAuthStore();

// Gate on what the target actually requires: the `back-office` route's meta
// demands `backoffice.reporting` VIEW (routes.ts), so a broader any-backoffice
// check could offer a button that bounces to a bare 403.
const hasBackOfficeAccess = computed(() =>
  authStore.hasUserAnyScopePermission(
    'backoffice.reporting',
    PermissionAction.VIEW,
  ),
);

// The back-office route lives under `:language`; /unauthorized is top-level,
// so the param must be resolved here rather than inherited from the URL.
const backOfficeRoute = computed(() => ({
  name: 'back-office',
  params: { language: resolveLanguage(route) },
}));

function formatPermissionName(permissionPath: string): string {
  const parts = permissionPath.split('.');
  const lastPart = parts[parts.length - 1];

  return lastPart
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

function formatActionName(action: string): string {
  return action.charAt(0).toUpperCase() + action.slice(1).toLowerCase();
}

const permissionPath = computed(() => {
  const perm = route.query.permission;
  return typeof perm === 'string' ? perm : null;
});

const action = computed(() => {
  const act = route.query.action;
  return typeof act === 'string' ? act : null;
});

const permissionMessage = computed(() => {
  if (!permissionPath.value || !action.value) {
    return null;
  }

  const permissionName = formatPermissionName(permissionPath.value);
  const actionName = formatActionName(action.value);

  return `You need '${permissionName} ${actionName}' permission to access this page`;
});

const reason = computed(() =>
  typeof route.query.reason === 'string' ? route.query.reason : null,
);

/**
 * Landed here for a reason that loops right back to this same page: no unit
 * assigned, or no globally-open year. Either way "Home" re-enters
 * `redirectToDefaultRoute`, which finds the same missing precondition and
 * bounces the user straight back here — so these need the Logout escape
 * hatch instead of a "Home" button.
 */
const isDeadEndReason = computed(
  () => reason.value === 'no-unit' || reason.value === 'no-open-year',
);

/** Localised message for a known redirect `reason` (e.g. `no-unit`), if any. */
const reasonMessage = computed(() => {
  const key = unauthorizedReasonMessageKey(reason.value);
  return key ? t(key) : null;
});

/** The single highlighted box: reason message wins over the permission hint. */
const highlightMessage = computed(
  () => reasonMessage.value ?? permissionMessage.value,
);

const homeRoute = computed(() => {
  const language = currentLanguage();
  return {
    name: DEFAULT_ROUTE_NAME,
    params: { language },
  };
});

/**
 * The only guaranteed escape from this page: `authStore.logout` clears the
 * server session cookies (localStorage alone won't) and redirects to the
 * login page. DELETE /session has no permission dependency, so it succeeds
 * even when every other call 403s (e.g. a stale account after a DB reset).
 */
async function onLogout() {
  await authStore.logout(router);
}
</script>
