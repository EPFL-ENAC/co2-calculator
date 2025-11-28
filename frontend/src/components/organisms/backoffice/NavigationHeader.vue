<script setup lang="ts">
import { NavItem } from 'src/constant/navigation';

defineProps<{
  item: NavItem;
}>();
</script>

<template>
  <div>
    <div class="q-my-xl q-px-xl">
      <div class="flex items-center q-gutter-md">
        <q-icon :name="item.icon" size="sm" color="accent" />
        <span class="text-h3 text-weight-bold">
          {{ $t(item.routeName) }}
        </span>
      </div>
      <span v-if="item.description" class="text-body1 text-secondary">
        {{ $t(item.description) }}
      </span>
    </div>
    <q-separator />
  </div>
</template>
