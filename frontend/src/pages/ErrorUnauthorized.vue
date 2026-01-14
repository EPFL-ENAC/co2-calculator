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

          <!-- Permission Message -->
          <div
            v-if="permissionMessage"
            class="q-pa-md rounded-borders bg-orange-1"
            style="max-width: 100%"
          >
            <div class="row items-center q-gutter-x-sm justify-center">
              <q-icon name="o_info" size="sm" color="orange-8" />
              <p class="text-body1 text-weight-medium text-orange-9 q-ma-none">
                {{ permissionMessage }}
              </p>
            </div>
          </div>

          <div class="q-px-lg" style="max-width: 600px">
            <p class="text-body1 text-grey-6 q-ma-none">
              {{ t('unauthorized_message') }}
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
import { useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';
import { WORKSPACE_SETUP_ROUTE_NAME } from 'src/router/routes';
import { i18n } from 'src/boot/i18n';

const route = useRoute();
const { t } = useI18n();

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

const homeRoute = computed(() => {
  const currentLocale = i18n.global.locale.value;
  const language = currentLocale.split('-')[0] || 'en';
  return {
    name: WORKSPACE_SETUP_ROUTE_NAME,
    params: { language },
  };
});
</script>
