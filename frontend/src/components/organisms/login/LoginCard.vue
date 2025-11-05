<script lang="ts" setup>
import { ref, computed } from 'vue';
import { storeToRefs } from 'pinia';
import Input from 'src/components/atoms/Input.vue';
import Button from 'src/components/atoms/Button.vue';
import { useAuthStore } from 'src/stores/auth';

const authStore = useAuthStore();
const { loading } = storeToRefs(authStore);

const username = ref('');
const password = ref('');

const errors = ref<{
  username?: string;
  password?: string;
  general?: string;
}>({});

const validateForm = (): boolean => {
  errors.value = {};

  if (!username.value.trim()) {
    errors.value.username = 'login_error_username_required';
  }

  if (!password.value.trim()) {
    errors.value.password = 'login_error_password_required';
  }

  return Object.keys(errors.value).length === 0;
};

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
  <div class="login-card">
    <!-- login form (stacked inputs) -->
    <q-form class="q-gutter-y-xl" @submit.prevent="handleSubmit">
      <!-- Logo + Title -->
      <div class="login__brand col-12">
        <img
          src="epfl-logo.svg"
          :alt="$t('login_logo_alt')"
          class="login__logo"
        />
        <h2 class="text-weight-medium">{{ $t('login_title') }}</h2>
      </div>

      <!-- submit button -->
      <div class="login__button">
        <Button
          html-type="submit"
          :fullwidth="true"
          :label="buttonLabel"
          :disabled="loading"
          size="md"
        />
      </div>
    </q-form>
  </div>
</template>
