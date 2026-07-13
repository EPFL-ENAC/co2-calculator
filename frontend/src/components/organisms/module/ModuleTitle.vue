<template>
  <q-card flat class="module-title-card relative container">
    <q-card-section>
      <div class="row justify-between items-start">
        <div class="title-group">
          <div class="title-row">
            <ModuleIconBox v-if="type" :name="type" size="sm" />
            <h1 class="text-h3 text-weight-medium q-mb-none">
              {{ $t(`${type}`) }}
            </h1>
          </div>
          <p
            v-if="hasDescription"
            class="text-body1 text-grey-7 q-mb-none q-mt-sm"
          >
            {{ $t(`${type}-description`) }}
          </p>
          <p
            v-if="hasDescriptionSubtext"
            class="subtext text-caption text-grey-5 q-mb-none q-mt-xs q-mb-lg"
          >
            {{ $t(`${type}-title-subtext`) }}
          </p>
          <a
            v-if="documentationLink"
            :href="documentationLink"
            target="_blank"
            rel="noopener noreferrer"
            class="doc-link text-caption text-grey-6 q-mt-sm"
          >
            <q-icon :name="outlinedArticle" size="16px" class="q-mr-xs" />
            {{ documentationTitle }}
          </a>
        </div>
        <q-icon
          v-if="tooltipText"
          :name="outlinedInfo"
          size="sm"
          class="cursor-pointer"
          :aria-label="$t('module-info-label')"
        >
          <q-tooltip anchor="center right" self="top right" class="u-tooltip">
            {{ tooltipText }}
          </q-tooltip>
        </q-icon>
      </div>
    </q-card-section>
  </q-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';
import {
  outlinedArticle,
  outlinedInfo,
} from '@quasar/extras/material-icons-outlined';
import { Module } from 'src/constant/modules';
import ModuleIconBox from 'src/components/atoms/ModuleIconBox.vue';

const props = withDefaults(
  defineProps<{
    type: Module;
    hasDescription?: boolean;
    hasDescriptionSubtext?: boolean;
  }>(),
  {
    hasDescription: false,
    hasDescriptionSubtext: false,
  },
);

const { t, te } = useI18n();
const tooltipText = computed(() => t(`module-${props.type}-title`));

// Per-module documentation link: label + URL live in each module's i18n file.
// Rendered only when the module defines a non-empty link.
const documentationLink = computed(() => {
  const key = `${props.type}-documentation-link`;
  return te(key) ? t(key) : '';
});
const documentationTitle = computed(() => {
  const key = `${props.type}-documentation-title`;
  return te(key) && t(key) ? t(key) : t('documentation');
});
</script>

<style scoped lang="scss">
@use 'src/css/02-tokens' as tokens;

.module-title-card {
  height: 100%;
}

.title-group {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
}

.title-row {
  display: flex;
  align-items: center;
  gap: tokens.$spacing-md;
}

// Preserve authored line breaks / blank lines so bullet lists in the
// subtext render as intended instead of collapsing into one run-on line.
.subtext {
  white-space: pre-line;
}

.doc-link {
  display: inline-flex;
  align-items: center;
  width: fit-content;
  text-decoration: none;

  &:hover {
    text-decoration: underline;
  }
}
</style>
