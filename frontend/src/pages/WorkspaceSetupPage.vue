<script setup lang="ts">
import { useAuthStore } from 'src/stores/auth';
import { useRouter } from 'vue-router';

const authStore = useAuthStore();
const router = useRouter();

const handleLogout = async () => {
  await authStore.logout(router);
};
</script>

<template>
  <q-page>
    <h1 class="text-h1">Workspace Setup</h1>

    <q-btn
      html-type="submit"
      :fullwidth="true"
      :label="'logout'"
      size="md"
      class="text-weight-medium"
      color="accent"
      text-color="white"
      @click="handleLogout"
      no-caps
    />
  </q-page>
</template>
