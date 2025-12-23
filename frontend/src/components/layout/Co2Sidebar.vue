<script setup lang="ts">
import { computed } from 'vue';
import { NavItem } from 'src/constant/navigation';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'src/stores/auth';
import { ROLES } from 'src/constant/roles';

interface Props {
  items: Record<string, NavItem>;
}

defineProps<Props>();
const router = useRouter();
const authStore = useAuthStore();

function navigateToRoute(routeName: string) {
  router.push({ name: routeName });
}

const hasBackOfficeStandardOnly = computed(() => {
  if (!authStore.user) return false;
  const userRoles = authStore.user.roles_raw.map((r) => r.role);
  const hasStandard = userRoles.includes(ROLES.BackOfficeStandard);
  const hasAdmin = userRoles.includes(ROLES.BackOfficeAdmin);
  // User has BackOfficeStandard but NOT BackOfficeAdmin
  return hasStandard && !hasAdmin;
});

function isItemDisabled(item: NavItem): boolean {
  return item.limitedAccess === true && hasBackOfficeStandardOnly.value;
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
