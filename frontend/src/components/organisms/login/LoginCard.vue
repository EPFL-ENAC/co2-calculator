<script lang="ts" setup>
import { computed, ref } from 'vue';
import { storeToRefs } from 'pinia';
import { useAuthStore } from 'src/stores/auth';
import { useI18n } from 'vue-i18n';

const authStore = useAuthStore();
const { loading } = storeToRefs(authStore);
const { t } = useI18n();

interface Props {
  mode?: 'test' | 'prod';
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'prod',
});

const form = ref(null);
const role = ref('co2.user.std');

const roleOptions = computed(() => [
  'co2.user.std',
  'co2.backoffice.admin',
  'co2.backoffice.std',
]);
const isTestMode = computed(() => props.mode === 'test');

function validate() {
  form.value.validate().then((success) => {
    if (success) {
      if (props.mode === 'test') {
        authStore.login_test(role.value);
      } else {
        authStore.login();
      }
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
          src="/epfl-logo.svg"
          :alt="$t('login_logo_alt')"
          class="login__logo"
          width="125px"
        />
        <h2 class="text-weight-medium">{{ $t('login_title') }}</h2>
      </div>

      <div v-if="isTestMode">
        <q-select
          v-model="role"
          filled
          :options="roleOptions"
          :label="$t('login_test_role_label')"
          :disable="loading"
          dense
          class="full-width"
        />
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
          no-caps
          @click="validate"
        />
      </div>
    </q-form>
  </q-card>
</template>
