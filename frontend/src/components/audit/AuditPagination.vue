<script setup lang="ts">
import { computed } from 'vue';

interface Props {
  page: number;
  pageSize: number;
  total: number;
}

const props = defineProps<Props>();
const emit = defineEmits<{
  'update:page': [value: number];
  'update:pageSize': [value: number];
}>();

const pageSizeOptions = [10, 25, 50, 100];

const lastPage = computed(() =>
  Math.max(1, Math.ceil(props.total / props.pageSize)),
);

const showingStart = computed(() =>
  props.total > 0 ? (props.page - 1) * props.pageSize + 1 : 0,
);

const showingEnd = computed(() =>
  Math.min(props.page * props.pageSize, props.total),
);

function prevPage() {
  if (props.page > 1) {
    emit('update:page', props.page - 1);
  }
}

function nextPage() {
  if (props.page < lastPage.value) {
    emit('update:page', props.page + 1);
  }
}

function cyclePageSize() {
  const currentIndex = pageSizeOptions.indexOf(props.pageSize);
  const nextIndex = (currentIndex + 1) % pageSizeOptions.length;
  emit('update:pageSize', pageSizeOptions[nextIndex]);
}
</script>

<template>
  <div class="audit-pagination">
    <span class="info-text">
      Showing {{ showingStart }}–{{ showingEnd }} of
      {{ $nOrDash(total) }} entries
      <span class="separator">|</span>
      Rows per page:
    </span>
    <q-btn flat dense class="rows-btn" @click="cyclePageSize">
      {{ pageSize }}
      <q-icon name="unfold_more" size="14px" />
    </q-btn>
    <q-btn
      flat
      dense
      round
      icon="chevron_left"
      size="sm"
      :disable="page === 1"
      @click="prevPage"
    />
    <span class="page-info">{{ page }} / {{ lastPage }}</span>
    <q-btn
      flat
      dense
      round
      icon="chevron_right"
      size="sm"
      :disable="page === lastPage"
      @click="nextPage"
    />
  </div>
</template>

<style scoped lang="scss">
.audit-pagination {
  height: 50px;
  border-top: 1px solid #c1c1c1;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 8px;
  background: #ffffff;

  .info-text {
    font-size: 14px;
    color: #707070;

    .separator {
      margin: 0 4px;
    }
  }

  .rows-btn {
    min-width: 43px;
    height: 34px;
    border: 1px solid #8e8e8e;
    border-radius: 3px;
    font-size: 14px;
  }

  .page-info {
    font-size: 14px;
    color: #707070;
    min-width: 50px;
    text-align: center;
  }
}
</style>
