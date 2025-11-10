<script lang="ts" setup>
import { computed, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from 'src/stores/auth';
import { useI18n } from 'vue-i18n';

const authStore = useAuthStore();
const { loading } = storeToRefs(authStore);
const { t } = useI18n();

const form = ref(null);

function validate() {
  form.value.validate().then((success) => {
    if (success) {
      authStore.login();
    } else {
      console.log('Form is invalid');
    }
  });
}

const handleSubmit = async (event: SubmitEvent) => {
  event.preventDefault();
  validate();
};

const buttonLabel = computed(() => {
  return loading.value ? t('login_button_loading') : t('login_button_submit');
});
</script>

<template>
  <q-card class="q-pa-xl login-card">
    <!-- login form (stacked inputs) -->
    <q-form ref="form" class="q-gutter-y-xl" @submit.prevent="handleSubmit">
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
          @click="validate"
          no-caps
        />
      </div>
    </q-form>
  </q-card>
</template>
