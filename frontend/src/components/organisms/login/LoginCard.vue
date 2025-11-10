<script lang="ts" setup>
import { computed } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from 'src/stores/auth';

const authStore = useAuthStore();
const { loading } = storeToRefs(authStore);

const handleSubmit = async (event: SubmitEvent) => {
  event.preventDefault();

  console.log('handleSubmit');

  authStore.login();
};

const buttonLabel = computed(() => {
  return loading.value ? 'Connecting...' : 'Login';
});
</script>

<template>
  <q-card class="q-pa-xl login-card">
    <!-- login form (stacked inputs) -->
    <q-form class="q-gutter-y-xl" @submit.prevent="handleSubmit">
      <!-- Logo + Title -->
      <div class="q-gutter-sm flex flex-center column">
        <q-img
          src="epfl-logo.svg"
          :alt="$t('login_logo_alt')"
          class="login__logo"
          width="100px"
        />
        <h2 class="text-weight-medium">{{ $t('login_title') }}</h2>
      </div>

      <!-- submit button -->
      <div class="login__button">
        <q-btn
          html-type="submit"
          :fullwidth="true"
          :label="buttonLabel"
          :disabled="loading"
          size="md"
          class="co2-button full-width text-weight-medium"
          color="accent"
          text-color="white"
          width="100px"
          @click="handleSubmit"
          no-caps
        />
      </div>
    </q-form>
  </q-card>
</template>
