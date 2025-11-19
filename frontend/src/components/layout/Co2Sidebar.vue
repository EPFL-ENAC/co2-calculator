<script setup lang="ts">
import { SidebarNavItem } from 'src/constant/sidebarNavigation';
import { useRouter, useRoute } from 'vue-router';
import { useI18n } from 'vue-i18n';

interface Props {
  items: Record<string, SidebarNavItem>;
}

defineProps<Props>();
const router = useRouter();
const { t } = useI18n();
const route = useRoute();
function navigateToRoute(routeName: string) {
  router.push({ name: routeName });
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
      clickable
      @click="navigateToRoute(item.routeName)"
    >
      <q-icon :name="item.icon" size="sm" />
      <q-item-label class="text-body2">{{ $t(item.routeName) }}</q-item-label>
    </q-item>
  </q-list>
</template>
