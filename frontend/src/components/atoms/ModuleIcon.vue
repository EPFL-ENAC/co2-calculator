<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue';
import type { Module } from 'src/constant/modules';

const props = defineProps<{
  module: Module;
  size?: 'sm' | 'md' | 'lg';
  color?: string;
}>();

const iconRef = ref<HTMLElement | null>(null);

// Load SVG content and insert it safely
const loadSvg = async () => {
  if (!iconRef.value) return;

  try {
    const response = await fetch(`/icons/modules/${props.module}.svg`);
    const svgText = await response.text();

    // Parse the SVG text into a DOM element
    const parser = new DOMParser();
    const svgDoc = parser.parseFromString(svgText, 'image/svg+xml');
    const svgElement = svgDoc.documentElement;

    // Clear existing content
    iconRef.value.innerHTML = '';

    // Append the parsed SVG element
    iconRef.value.appendChild(svgElement);
  } catch (error) {
    console.error(`Failed to load SVG for ${props.module}:`, error);
  }
};

onMounted(async () => {
  await nextTick();
  loadSvg();
});

watch(
  () => props.module,
  async () => {
    await nextTick();
    loadSvg();
  },
);
</script>

<template>
  <span
    ref="iconRef"
    class="module-icon"
    :class="[size ? `module-icon--${size}` : '', color ? `text-${color}` : '']"
  />
</template>
