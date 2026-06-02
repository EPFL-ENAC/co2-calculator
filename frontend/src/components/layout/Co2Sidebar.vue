<script setup lang="ts">
import { computed, ref } from 'vue';
import { NavItem } from 'src/constant/navigation';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'src/stores/auth';
import { ROLES } from 'src/constant/roles';
import { PermissionAction } from 'src/constant/permissions';

interface Props {
  items: Record<string, NavItem>;
}

defineProps<Props>();
const router = useRouter();
const authStore = useAuthStore();
const collapsed = ref(false);

function navigateToRoute(routeName: string) {
  router.push({ name: routeName });
}

const hasBackOfficeEditPermission = computed(() => {
  return authStore.hasUserAnyScopePermission(
    'backoffice.users',
    PermissionAction.EDIT,
  );
});

const hasSuperAdminRole = computed(() => {
  // todo: replace with ROLES.SuperAdmin when done!
  return (
    authStore.user?.roles_raw?.some((x) => x.role === ROLES.BackOfficeMetier) ??
    false
  );
});

function isItemDisabled(item: NavItem): boolean {
  // Super-admin trumps all gates — SA sees every menu item.  Applies
  // to ``limitedAccess`` items too (Pipeline Operations, Data
  // Management, User Management), not just plain unrestricted ones —
  // there is no scenario where a SA should be locked out of a
  // back-office page.
  if (hasSuperAdminRole.value) return false;
  // if (item.superAdminOnly === true) return true;
  if (item.limitedAccess === true && !hasBackOfficeEditPermission.value)
    return true;
  return false;
}
</script>

<template>
  <div class="co2-sidebar" :class="{ 'co2-sidebar--collapsed': collapsed }">
    <div class="co2-sidebar-toggle" @click="collapsed = !collapsed">
      <q-icon :name="collapsed ? 'chevron_right' : 'chevron_left'" size="xs" />
    </div>
    <q-list class="co2-sidebar-items">
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
        <q-item-label v-show="!collapsed" class="text-body2">{{
          $t(item.routeName)
        }}</q-item-label>
        <q-tooltip v-if="collapsed" anchor="center right" self="center left">
          {{ $t(item.routeName) }}
        </q-tooltip>
      </q-item>
    </q-list>
  </div>
</template>
