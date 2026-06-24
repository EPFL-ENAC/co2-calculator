<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <q-card style="min-width: 500px">
      <q-card-section class="row items-center q-pb-none">
        <q-icon :name="iconName" size="sm" class="q-mr-sm" />
        <div class="text-h4 text-weight-medium">
          {{ title }}
        </div>
        <q-space />
        <q-btn
          v-close-popup
          flat
          size="md"
          :icon="outlinedClose"
          color="grey-6"
        />
      </q-card-section>

      <q-separator class="q-mt-sm" />

      <q-card-section>
        <q-input
          v-model="localNote"
          type="textarea"
          :placeholder="$t('common_comment_placeholder')"
          outlined
          rows="4"
        />
        <div class="text-caption text-grey q-mt-sm">
          {{ $t('common_note_hint') }}
        </div>
      </q-card-section>

      <q-card-actions class="q-px-md q-pb-md">
        <q-btn
          :label="submitLabel"
          :color="submitBtnColor"
          :style="submitBtnStyle"
          unelevated
          no-caps
          class="text-weight-medium"
          @click="onSave"
        />
        <q-btn
          v-if="mode === 'edit'"
          :label="$t('common_delete')"
          color="primary"
          unelevated
          no-caps
          outline
          class="text-weight-medium"
          @click="deleteNote"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, watch, computed } from 'vue';
import {
  outlinedAddComment,
  outlinedClose,
  outlinedEditNote,
} from '@quasar/extras/material-icons-outlined';
import { useI18n } from 'vue-i18n';

const { t: $t } = useI18n();

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    mode?: 'add' | 'edit';
    note?: string;
    moduleColor?: string;
    moduleTextColor?: string;
  }>(),
  {
    mode: 'add',
    note: undefined,
    moduleColor: undefined,
    moduleTextColor: undefined,
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'save', note: string): void;
  (e: 'delete'): void;
}>();

const localNote = ref(props.note ?? '');

const isEdit = computed(() => props.mode === 'edit');
const iconName = computed(() =>
  isEdit.value ? outlinedEditNote : outlinedAddComment,
);
const title = computed(() =>
  isEdit.value
    ? $t('common_edit_comment_title')
    : $t('common_comment_entry_title'),
);
const submitLabel = computed(() =>
  isEdit.value ? $t('common_edit') : $t('common_add_button'),
);

const submitBtnColor = computed(() =>
  props.moduleColor ? undefined : 'accent',
);

const submitBtnStyle = computed(() =>
  props.moduleColor
    ? {
        background: props.moduleColor,
        color: props.moduleTextColor ?? 'white',
        border: `1px solid ${props.moduleTextColor ?? 'white'}`,
      }
    : undefined,
);

watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      localNote.value = props.note ?? '';
    }
  },
);

function onSave() {
  emit('save', localNote.value.trim());
  emit('update:modelValue', false);
}

function deleteNote() {
  emit('delete');
  emit('update:modelValue', false);
}
</script>
