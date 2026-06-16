<script setup lang="ts">
import { computed } from 'vue';
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import { ROLES } from 'src/constant/roles';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const roles = computed(() => [
  {
    name: t(ROLES.StandardUser),
    id: ROLES.StandardUser,
    description: t('role_standard_description'),
  },
  {
    name: t(ROLES.PrincipalUser),
    id: ROLES.PrincipalUser,
    description: t('role_principal_description'),
  },
  {
    name: t(ROLES.BackOfficeMetier),
    id: ROLES.BackOfficeMetier,
    description: t('role_backoffice_description'),
  },
  {
    name: t(ROLES.SuperAdmin),
    id: ROLES.SuperAdmin,
    description: t('role_superadmin_description'),
  },
]);
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT" />
    <div class="q-my-xl q-px-xl">
      <div class="container full-width">
        <div class="text-body1 q-mb-xl">
          {{ $t('user_management_page_description') }}
        </div>
        <q-card flat bordered class="q-mb-xl">
          <q-card-section>
            <div class="text-subtitle1 text-weight-bold q-mb-sm">
              {{ $t('user_management_roles_title') }}
            </div>
            <q-list dense>
              <q-item
                v-for="role in roles"
                :key="role.id"
                dense
                class="q-px-none"
              >
                <span class="text-body2">
                  <span class="text-weight-medium">{{ role.name }}</span>
                  ({{ role.id }}) {{ role.description }}
                </span>
              </q-item>
            </q-list>
          </q-card-section>
        </q-card>
        <q-btn
          no-caps
          :label="$t('user_management_page_button_label')"
          color="accent"
          size="md"
          class="q-mr-sm text-weight-medium"
          external
          :href="'https://accred.epfl.ch?opentab=authorizations'"
          rel="noopener noreferrer"
        />
        <q-btn
          outline
          no-caps
          :label="$t('user_management_page_button_documentation_label')"
          color="primary"
          size="md"
          class="text-weight-medium"
          :to="{ name: 'back-office-documentation' }"
        />
      </div>
    </div>
  </q-page>
</template>
