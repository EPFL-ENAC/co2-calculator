<script setup lang="ts">
import { BACKOFFICE_NAV } from 'src/constant/navigation';
import NavigationHeader from 'src/components/organisms/backoffice/NavigationHeader.vue';
</script>

<template>
  <q-page>
    <navigation-header :item="BACKOFFICE_NAV.BACKOFFICE_USER_MANAGEMENT" />
    <div class="q-my-xl q-px-xl">
      <div class="container full-width">
        <div class="text-body1 q-mb-xl">
          {{ $t('user_management_page_description_system') }}
        </div>
        <q-btn
          no-caps
          :label="$t('user_management_page_button_label_system')"
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
          :label="$t('user_management_page_button_label_outline_system')"
          color="primary"
          size="md"
          class="text-weight-medium"
          :to="{ name: 'back-office-documentation' }"
        />
      </div>
    </div>
  </q-page>
</template>
