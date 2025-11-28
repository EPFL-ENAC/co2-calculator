<script setup lang="ts">
import { NavItem } from 'src/constant/navigation';
import { useRouter } from 'vue-router';

interface Props {
  items: Record<string, NavItem>;
}

defineProps<Props>();
const router = useRouter();
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
