<script setup lang="ts">
import { computed } from 'vue';
import { NavItem } from 'src/constant/navigation';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'src/stores/auth';
import { hasPermission } from 'src/utils/permission';

interface Props {
  items: Record<string, NavItem>;
}

defineProps<Props>();
const router = useRouter();
const authStore = useAuthStore();

function navigateToRoute(routeName: string) {
  router.push({ name: routeName });
}

const hasBackOfficeEditPermission = computed(() => {
  return hasPermission(authStore.user?.permissions, 'backoffice.users', 'edit');
});

function isItemDisabled(item: NavItem): boolean {
  // Items with limitedAccess require edit permission
  // If user doesn't have edit permission, disable limitedAccess items
  return item.limitedAccess === true && !hasBackOfficeEditPermission.value;
}
</script>

<template>
  <q-list class="co2-sidebar">
    <q-item
      v-for="item in items"
      :key="item.routeName"
      class="co2-sidebar-item"
      :class="{
        'co2-sidebar-item--selected':
          router.currentRoute.value.name === item.routeName,
      }"
      :disable="isItemDisabled(item)"
      clickable
      @click="!isItemDisabled(item) && navigateToRoute(item.routeName)"
    >
      <q-icon :name="item.icon" size="sm" />
      <q-item-label class="text-body2">{{ $t(item.routeName) }}</q-item-label>
    </q-item>
  </q-list>
</template>
