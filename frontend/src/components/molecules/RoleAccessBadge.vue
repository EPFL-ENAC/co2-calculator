<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useWorkspaceStore } from '@/stores/workspace';
import { useAuthStore } from '@/stores/auth';
import { runtimeConfig } from '@/config/runtime';

const workspaceStore = useWorkspaceStore();
const authStore = useAuthStore();
const { t } = useI18n();

// Principal (unit-breadth) users can validate module status; standard (own)
// users cannot. We use the same signal to tailor the access copy.
const isPrincipalUser = computed(() =>
  authStore.hasUserCanValidateModuleStatus(),
);

// Drives the role-scoped i18n keys (co2_calculator_role_*, _access_*_title/_body).
const userType = computed(() =>
  isPrincipalUser.value ? 'principal' : 'standard',
);

// Access-management portal (name + URL), configurable per deployment via
// APP_ACCESS_MANAGEMENT_PROVIDER_* — see src/config/runtime.ts. No default: when
// unset the popover CTA link is hidden. Principals delegate roles here; standard
// users instead email the principal.
const accessManagementProviderName = runtimeConfig.accessManagementProviderName;
const accessManagementProviderUrl = runtimeConfig.accessManagementProviderUrl;
const accessManagementProviderAboutUrl =
  runtimeConfig.accessManagementProviderAboutUrl;
const rolesDocUrl = runtimeConfig.rolesDocUrl;

const principalUserName = computed(
  () => workspaceStore.selectedUnit?.principal_user_name ?? '',
);

// Standard users request access by emailing the unit's principal user, with a
// pre-filled subject/body. Null when no principal email is known for the unit.
const requestAccessMailto = computed(() => {
  const email = workspaceStore.selectedUnit?.principal_user_email;
  if (!email) return null;
  const unit = workspaceStore.selectedUnit?.name ?? '';
  const subject = t('co2_calculator_access_mail_subject', { unit });
  const body = t('co2_calculator_access_mail_body', {
    name: principalUserName.value,
    unit,
  });
  return `mailto:${email}?subject=${encodeURIComponent(
    subject,
  )}&body=${encodeURIComponent(body)}`;
});
</script>

<template>
  <!-- Discreet role badge; opens a popover explaining the access level and
       how to request more (via the configured authorization provider). -->
  <q-btn
    flat
    dense
    no-caps
    size="sm"
    class="role-access-badge"
    :class="{ 'role-access-badge--principal': isPrincipalUser }"
  >
    <q-icon
      :name="isPrincipalUser ? 'o_verified_user' : 'o_lock'"
      size="xs"
      class="q-mr-xs"
    />
    {{ $t(`co2_calculator_role_${userType}`) }}
    <q-icon name="expand_more" size="xs" class="q-ml-xs" />
    <q-menu anchor="bottom right" self="top right" :offset="[0, 6]">
      <div class="role-access-badge__popover">
        <div>
          <p class="text-subtitle2 text-weight-medium q-mb-xs">
            {{ $t(`co2_calculator_access_${userType}_title`) }}
          </p>
          <p class="text-body2 text-secondary q-mb-none">
            {{
              $t(`co2_calculator_access_${userType}_body`, {
                provider:
                  accessManagementProviderName ||
                  $t('co2_calculator_access_provider_generic'),
              })
            }}
          </p>
        </div>

        <!-- Standard users email their unit's principal user. -->
        <q-btn
          v-if="!isPrincipalUser && requestAccessMailto"
          type="a"
          :href="requestAccessMailto"
          color="info"
          icon="o_mail"
          :label="$t('co2_calculator_access_cta_standard')"
          unelevated
          no-caps
          size="sm"
          class="text-weight-medium self-start"
        />
        <p
          v-else-if="!isPrincipalUser"
          class="text-body2 text-secondary q-mb-none"
        >
          {{
            $t('co2_calculator_access_no_email', {
              name: principalUserName,
            })
          }}
        </p>

        <div class="role-access-badge__links">
          <a
            v-if="rolesDocUrl"
            :href="rolesDocUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="link text-body2 text-weight-medium"
          >
            {{ $t('co2_calculator_access_cta_roles_doc') }}
            <q-icon name="o_arrow_outward" size="xs" />
          </a>

          <a
            v-if="accessManagementProviderAboutUrl"
            :href="accessManagementProviderAboutUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="link text-body2 text-weight-medium"
          >
            {{
              $t('co2_calculator_access_cta_about_provider', {
                provider:
                  accessManagementProviderName ||
                  $t('co2_calculator_access_provider_generic'),
              })
            }}
            <q-icon name="o_arrow_outward" size="xs" />
          </a>

          <!-- Principals delegate roles in the access-management portal;
               hidden when no portal URL is configured. -->
          <a
            v-if="isPrincipalUser && accessManagementProviderUrl"
            :href="accessManagementProviderUrl"
            target="_blank"
            rel="noopener noreferrer"
            class="link text-body2 text-weight-medium"
          >
            {{
              $t('co2_calculator_access_cta_principal', {
                provider:
                  accessManagementProviderName ||
                  $t('co2_calculator_access_provider_generic'),
              })
            }}
            <q-icon name="o_arrow_outward" size="xs" />
          </a>
        </div>
      </div>
    </q-menu>
  </q-btn>
</template>

<style scoped lang="scss">
@use '@/css/02-tokens' as tokens;

// Neutral pill, color keyed to role, opens the access popover below.
.role-access-badge {
  color: tokens.$color-text;
  border: 1px solid tokens.$color-text;
  border-radius: tokens.$radius-pill;
  padding: 2px tokens.$spacing-sm;
  flex-shrink: 0;

  &--principal {
    color: tokens.$color-validated;
    border-color: tokens.$color-validated;
  }
}

// Access details revealed from the role badge.
.role-access-badge__popover {
  display: flex;
  flex-direction: column;
  gap: tokens.$spacing-lg;
  max-width: 400px;
  padding: tokens.$spacing-xl;
}

.role-access-badge__links {
  display: flex;
  flex-direction: column;
  gap: tokens.$spacing-md;
  align-items: flex-start;
}
</style>
