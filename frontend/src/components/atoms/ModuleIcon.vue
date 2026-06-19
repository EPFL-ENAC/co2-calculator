<script setup lang="ts">
import { computed, type Directive } from 'vue';
import { icons } from 'src/plugin/module-icon';

const props = withDefaults(
  defineProps<{
    name: string;
    size?: 'sm' | 'md' | 'lg';
    color?: string; // e.g., 'primary', 'accent', 'grey-8';
  }>(),
  {
    size: 'md',
    color: 'accent',
  },
);

const svgContent = computed(() => icons[props.name] || '');

// Render trusted, build-time SVG strings without innerHTML: DOMParser builds an
// inert document, so parsed <script> nodes never execute when inserted.
const renderSvg = (el: HTMLElement, svg: string) => {
  if (!svg) {
    el.replaceChildren();
    return;
  }
  const doc = new DOMParser().parseFromString(svg, 'image/svg+xml');
  el.replaceChildren(document.importNode(doc.documentElement, true));
};

const vSvg: Directive<HTMLElement, string> = {
  mounted: (el, binding) => renderSvg(el, binding.value),
  updated: (el, binding) => renderSvg(el, binding.value),
};

const iconClass = computed(() => [
  'module-icon',
  `module-icon--${props.size}`,
  props.color ? `text-${props.color}` : '',
]);
</script>

<template>
  <span v-svg="svgContent" :class="iconClass" />
</template>
