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
    <Button :label="'logout'" @click="handleLogout" />
  </q-page>
</template>
