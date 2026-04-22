<template>
  <section class="page" :class="{ 'page--first': isFirst }">
    <header v-if="title || pageNumber != null" class="page__header">
      <div class="page__title">
        <q-img src="/epfl-logo.svg" :alt="$t('logo_alt')" width="75px" />
        <span class="q-ml-md text-h5 text-weight-medium">{{
          $t('calculator_title')
        }}</span>
      </div>
      <div class="page__number">
        <span v-if="pageNumber != null">{{ pageNumber }}</span>
      </div>
    </header>

    <div class="page__content">
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
interface Props {
  title?: string;
  pageNumber?: number;
  isFirst?: boolean;
}

withDefaults(defineProps<Props>(), {
  title: undefined,
  pageNumber: undefined,
  isFirst: false,
});
</script>

<style scoped lang="scss">
.page {
  width: 210mm;
  height: 297mm;
  overflow: hidden;
  padding: 10mm;
  background: white;
  color: black;
  box-sizing: border-box;
  margin: 12px 0;

  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;

  display: flex;
  flex-direction: column;
}

.page__header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 5mm;
}

.page__title {
  font-weight: 600;
  font-size: 14px;
}

.page__number {
  font-size: 12px;
  opacity: 0.7;
}

.page__content {
  flex: 1;
  min-height: 0;
}

.page--first .page__header {
  margin-bottom: 10mm;
}

@media print {
  .page {
    margin: 0;
    page-break-after: always;
    break-after: page;
  }
}
</style>
