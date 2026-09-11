<template>
  <div
    v-if="!editing"
    :ref="onShellMounted"
    class="inline-cell"
    :class="{
      'inline-cell--editable': canActivate,
      'inline-cell--select': canActivate && affordance === 'select',
      'inline-cell--input': canActivate && affordance === 'input',
      'inline-cell--placeholder': textIsPlaceholder,
      'inline-cell--required-empty': requiredEmpty,
    }"
    :role="canActivate ? 'button' : undefined"
    :tabindex="canActivate ? 0 : undefined"
    :aria-label="canActivate ? editLabel : undefined"
    :title="title"
    @click="activate"
    @keydown.enter.prevent="activate"
    @keydown.space.prevent="activate"
  >
    <span class="inline-cell__text">{{ text }}</span>
    <q-icon
      v-if="canActivate"
      class="inline-cell__icon"
      :name="affordance === 'select' ? matExpandMore : outlinedEdit"
    />
  </div>
  <div
    v-else
    class="inline-cell inline-cell--editing"
    @keydown.esc.stop="cancel"
    @keydown.enter="onEditorEnter"
  >
    <slot />
  </div>
</template>

<script setup lang="ts">
import { matExpandMore } from '@quasar/extras/material-icons';
import { outlinedEdit } from '@quasar/extras/material-icons-outlined';
import { computed } from 'vue';

const props = defineProps<{
  text: string;
  textIsPlaceholder?: boolean;
  locked: boolean;
  disabled: boolean;
  affordance: 'input' | 'select';
  requiredEmpty?: boolean;
  title?: string;
  editLabel: string;
}>();

const editing = defineModel<boolean>('editing', { default: false });

const emit = defineEmits<{ cancel: [] }>();

const canActivate = computed(() => !props.locked && !props.disabled);

let returnFocus = false;

function activate() {
  if (!canActivate.value) return;
  returnFocus = true;
  editing.value = true;
}

function cancel() {
  emit('cancel');
  editing.value = false;
}

function onEditorEnter(event: KeyboardEvent) {
  if (props.affordance !== 'input') return;
  (event.target as HTMLElement | null)?.blur();
}

function onShellMounted(el: unknown) {
  if (!returnFocus || !(el instanceof HTMLElement)) return;
  returnFocus = false;
  if (document.activeElement === document.body) {
    el.focus({ preventScroll: true });
  }
}
</script>
