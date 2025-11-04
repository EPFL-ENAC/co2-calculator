<script lang="ts" setup>
import { ref } from 'vue';
import Input from 'src/components/atoms/Input.vue';
import Button from 'src/components/atoms/Button.vue';

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

  // Clear previous errors
  errors.value = {};

  // Validate form
  if (!validateForm()) {
    // Clear password if validation fails
    if (errors.value.username || errors.value.password) {
      password.value = '';
    }
    return;
  }

  // TODO: Replace with actual API call
  /*
  try {
    await login(username.value, password.value);
  } catch (error) {
    if (error.status === 401) {
      errors.value.password = 'login_error_password_incorrect';
      username.value = '';
      password.value = '';
    } else {
      errors.value.general = 'login_error_general';
    }
  }
  */

  // Simulated validation for demonstration
  // Remove this when implementing actual API
  if (username.value !== '1234' || password.value !== '1234') {
    errors.value.password = 'login_error_password_incorrect';
    username.value = '';
    password.value = '';
  }
};
</script>

<template>
  <div class="login-card q-pa-lg">
    <div class="q-gutter-md login__wrap">
      <!-- Logo + Title -->
      <div class="login__brand text-center">
        <img
          src="epfl-logo.svg"
          :alt="$t('login_logo_alt')"
          class="login__logo"
        />
        <h2 class="text-weight-medium">{{ $t('login_title') }}</h2>
      </div>

      <!-- login form (stacked inputs) -->
      <form class="login__form" @submit.prevent="handleSubmit">
        <div class="login__field">
          <Input
            v-model="username"
            :placeholder="$t('login_input_username_placeholder')"
            :error="!!errors.username"
          />
          <p v-if="errors.username" class="login__error">
            {{ $t(errors.username) }}
          </p>
        </div>
        <div class="login__field">
          <Input
            v-model="password"
            :placeholder="$t('login_input_password_placeholder')"
            type="password"
            :error="!!errors.password"
          />
          <p v-if="errors.password" class="login__error">
            {{ $t(errors.password) }}
          </p>
        </div>

        <!-- General error message -->
        <p v-if="errors.general" class="login__error login__error--general">
          {{ $t(errors.general) }}
        </p>

        <!-- submit button -->
        <div class="login__button">
          <Button html-type="submit" :fullwidth="true">{{
            $t('login_button_submit')
          }}</Button>
        </div>
      </form>
    </div>
  </div>
</template>
