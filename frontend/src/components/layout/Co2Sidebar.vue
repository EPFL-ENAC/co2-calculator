<script setup lang="ts">
import { ref } from 'vue';
import { NavItem } from 'src/constant/navigation';
import { useRouter } from 'vue-router';
import { useAuthStore } from 'src/stores/auth';
import { PermissionAction } from 'src/stores/auth';

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

function isItemDisabled(item: NavItem): boolean {
  // Page-driven gating (#862): reachability is derived from the target route's
  // own `meta.requiredPermission` — the single source of truth that the router
  // guard (`permissionGuard`) also enforces, so sidebar and router agree.
  // Checked any-scope so affiliation-suffixed keys match; super admin holds
  // every backoffice key and passes naturally.
  const meta = router.resolve({ name: item.routeName }).meta;
  const path = meta.requiredPermission as string | undefined;
  if (!path) return false;
  const action =
    (meta.requiredAction as PermissionAction | undefined) ??
    PermissionAction.VIEW;
  return !authStore.hasUserAnyScopePermission(path, action);
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
    <div class="co2-sidebar-docs-wrapper">
      <q-separator />
      <q-item
        class="co2-sidebar-item"
        tag="a"
        :href="$t('header_backoffice_documentation_link')"
        target="_blank"
        clickable
      >
        <q-icon name="o_article" size="sm" />
        <q-item-label v-show="!collapsed" class="text-body2">{{
          $t('backoffice_documentation_button_label')
        }}</q-item-label>
      </q-item>
    </div>
  </div>
</template>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.co2-sidebar-docs-wrapper {
  margin-top: auto;
  flex-shrink: 0;
}
</style>
