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

<!-- Not scoped: the SVG is injected at runtime via the v-svg directive, so its
     child nodes never receive Vue's scope attribute. `.module-icon` is only
     rendered by this component, so global scope is safe here. -->
<style lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-icon {
  width: tokens.$icon-size-md;
  height: tokens.$icon-size-md;
  display: inline-flex;
  align-items: center;
  justify-content: center;

  &--sm {
    width: tokens.$icon-size-sm;
    height: tokens.$icon-size-sm;
  }

  &--lg {
    width: tokens.$icon-size-lg;
    height: tokens.$icon-size-lg;
  }

  svg {
    width: 100%;
    height: 100%;
    color: inherit;

    // Override inline styles and classes to use currentcolor
    path,
    circle,
    rect,
    polygon,
    ellipse,
    g,
    .st0,
    [class*='st'] {
      fill: currentcolor;
    }

    // Override style tag inside SVG
    style {
      display: none;
    }
  }
}
</style>
