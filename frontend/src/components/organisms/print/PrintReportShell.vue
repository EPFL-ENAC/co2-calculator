<script setup lang="ts">
interface Props {
  /** Report data is still on its way. */
  loading?: boolean;
  /** Loaded, but there is nothing to report. */
  empty?: boolean;
  /** What to say on an empty report; nothing is shown without it. */
  emptyMessage?: string;
}

withDefaults(defineProps<Props>(), {
  loading: false,
  empty: false,
  emptyMessage: undefined,
});

function printReport() {
  window.print();
}
</script>

<template>
  <div class="bg-grey-2 print-report">
    <q-toolbar class="bg-ac text-primary q-py-sm print-toolbar print-hide">
      <q-space />
      <q-btn
        color="accent"
        icon="o_print"
        size="md"
        class="text-weight-medium"
        :label="$t('results_print')"
        @click="printReport"
      />
    </q-toolbar>

    <div v-if="loading" class="print-loading print-hide">
      <div class="print-loading__sheet" aria-hidden="true">
        <div class="print-loading__sheet-head">
          <span class="print-loading__bone print-loading__bone--brand" />
          <span class="print-loading__bone print-loading__bone--page" />
        </div>
        <span class="print-loading__bone print-loading__bone--title" />
        <span class="print-loading__bone" style="width: 46%" />
        <span class="print-loading__block" />
        <span class="print-loading__bone" style="width: 72%" />
        <span class="print-loading__bone" style="width: 88%" />
        <span class="print-loading__bone" style="width: 60%" />
      </div>

      <div class="print-loading__status" role="status" aria-live="polite">
        <div class="print-loading__label">{{ $t('print_report_loading') }}</div>
        <q-linear-progress
          indeterminate
          rounded
          size="6px"
          color="accent"
          track-color="grey-4"
          class="print-loading__bar"
        />
      </div>
    </div>

    <div v-else-if="empty" class="flex justify-center q-pa-xl print-hide">
      <span v-if="emptyMessage" class="text-body1">{{ emptyMessage }}</span>
    </div>

    <div v-else class="report-container">
      <slot />
    </div>
  </div>
</template>

<!-- Not scoped: these rules hide layout chrome (.q-header/.q-footer/.q-drawer)
     that lives outside this component, and reach into the .q-card elements the
     report pages render into the slot. -->
<style lang="scss">
@use 'src/css/02-tokens' as tokens;

.print-report {
  min-height: 100vh;
}

.report-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: tokens.$print-report-container-padding;
  color: tokens.$color-text;
}

.print-toolbar {
  position: sticky;
  top: 0;
  border-bottom: 1px solid var(--half-muted-color);
  z-index: tokens.$print-toolbar-z-index;
}

.print-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-height: 70vh;
  padding: tokens.$print-report-container-padding;

  &__sheet {
    display: flex;
    flex-direction: column;
    gap: 10px;
    width: 210mm;
    max-width: 100%;
    padding: 10mm;
    background: white;
    box-sizing: border-box;
    // Only the top of the sheet is drawn: it stands for a page still filling in,
    // not an empty one.
    mask-image: linear-gradient(to bottom, black 55%, transparent);
  }

  &__sheet-head {
    display: flex;
    justify-content: space-between;
    margin-bottom: 6px;
  }

  &__bone {
    display: block;
    height: 12px;
    width: 100%;
    border-radius: 4px;
    background: linear-gradient(90deg, #e9e9e9 0%, #f5f5f5 40%, #e9e9e9 80%);
    background-size: 300% 100%;
    animation: print-loading-shimmer 1.6s ease-in-out infinite;

    &--brand {
      width: 130px;
      height: 16px;
    }

    &--page {
      width: 20px;
      height: 12px;
    }

    &--title {
      height: 22px;
      width: 62%;
    }
  }

  &__block {
    display: block;
    height: 110px;
    border-radius: 6px;
    background: #f1f1f1;
  }

  &__status {
    width: 320px;
    max-width: 100%;
    margin-top: 24px;
    text-align: center;
  }

  &__label {
    font-size: 13px;
    font-weight: 500;
  }

  &__bar {
    margin-top: 10px;
  }
}

@keyframes print-loading-shimmer {
  from {
    background-position: 150% 0;
  }

  to {
    background-position: -150% 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .print-loading__bone {
    animation: none;
  }
}

@media print {
  .print-hide,
  .q-header,
  .q-footer,
  .q-drawer {
    display: none;
  }

  // A viewport-tall shell pushes the last page onto a trailing blank sheet.
  .print-report {
    min-height: 0;
  }

  .report-container {
    display: block;
    width: 100%;
    padding: 0;
  }

  .print-report .q-card,
  .print-report .q-card-section {
    box-shadow: none;
  }
}
</style>
