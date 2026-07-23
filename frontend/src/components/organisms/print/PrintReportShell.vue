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

    <div v-if="loading" class="flex justify-center q-pa-xl print-hide">
      <q-spinner color="accent" size="3em" />
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

@media print {
  .print-hide,
  .q-header,
  .q-footer,
  .q-drawer {
    display: none;
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
