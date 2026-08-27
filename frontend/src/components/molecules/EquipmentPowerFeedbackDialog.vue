<template>
  <q-dialog
    :model-value="modelValue"
    @update:model-value="$emit('update:modelValue', $event)"
    @before-show="resetState"
  >
    <q-card style="min-width: 520px; max-width: 90vw">
      <q-card-section class="row items-center q-pb-none">
        <q-icon :name="headerIcon" size="sm" class="q-mr-sm" />
        <div class="text-h4 text-weight-medium">
          {{ headerTitle }}
        </div>
        <q-space />
        <q-btn v-close-popup flat size="md" icon="o_close" color="grey-6" />
      </q-card-section>

      <q-separator class="q-mt-sm" />

      <q-tabs
        v-model="activeTab"
        no-caps
        align="left"
        class="feedback-tabs text-grey-7"
        :style="{ '--tab-accent': tabAccentColor }"
      >
        <q-tab
          name="comment"
          :label="$t('equipment-power-feedback-tab-comment')"
        />
        <q-tab name="power" :label="$t('equipment-power-feedback-tab-power')" />
      </q-tabs>

      <q-separator />

      <q-tab-panels v-model="activeTab" animated>
        <!-- Tab 1: Comment (mirrors NoteDialog) -->
        <q-tab-panel name="comment">
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
          <div class="q-mt-md">
            <q-btn
              :label="
                mode === 'edit' ? $t('common_edit') : $t('common_add_button')
              "
              :color="submitBtnColor"
              :style="submitBtnStyle"
              unelevated
              no-caps
              class="text-weight-medium q-mr-sm"
              @click="onSaveComment"
            />
            <q-btn
              v-if="mode === 'edit'"
              :label="$t('common_delete')"
              color="primary"
              unelevated
              no-caps
              outline
              class="text-weight-medium"
              @click="onDeleteComment"
            />
          </div>
        </q-tab-panel>

        <!-- Tab 2: Power change request -->
        <q-tab-panel name="power">
          <q-input
            v-model="requestText"
            type="textarea"
            outlined
            rows="12"
            autogrow
          />
          <div class="q-mt-md">
            <q-btn
              :href="feedbackMailtoHref"
              :label="$t('equipment-power-feedback-send')"
              :color="submitBtnColor"
              :style="submitBtnStyle"
              icon="o_mail"
              unelevated
              no-caps
              class="text-weight-medium"
              @click="onSendRequest"
            />
          </div>
        </q-tab-panel>
      </q-tab-panels>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { runtimeConfig } from '@/config/runtime';
import {
  buildPowerRequestBody,
  buildMailtoUrl,
} from '@/utils/equipmentPowerFeedbackMail';

const { t: $t } = useI18n();

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    note?: string;
    mode?: 'add' | 'edit';
    equipmentName: string;
    equipmentClass: string;
    subClass?: string | null;
    currentActivePowerW?: number | null;
    currentStandbyPowerW?: number | null;
    unitName: string;
    year: string | number;
    moduleColor?: string;
    moduleTextColor?: string;
    moduleAccentColor?: string;
  }>(),
  {
    note: undefined,
    mode: 'add',
    subClass: null,
    currentActivePowerW: null,
    currentStandbyPowerW: null,
    moduleColor: undefined,
    moduleTextColor: undefined,
    moduleAccentColor: undefined,
  },
);

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void;
  (e: 'save', note: string): void;
  (e: 'delete'): void;
}>();

const activeTab = ref<'comment' | 'power'>('comment');
const localNote = ref(props.note ?? '');
const requestText = ref('');

const headerIcon = computed(() =>
  activeTab.value === 'power' ? 'o_electric_bolt' : 'o_add_comment',
);
const headerTitle = computed(() =>
  activeTab.value === 'power'
    ? $t('equipment-power-feedback-title')
    : $t('common_comment_entry_title'),
);

const tabAccentColor = computed(
  () => props.moduleAccentColor ?? props.moduleTextColor ?? 'var(--q-primary)',
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

function computeRequestText(): string {
  return buildPowerRequestBody(
    {
      equipmentName: props.equipmentName,
      equipmentClass: props.equipmentClass,
      subClass: props.subClass,
      currentActivePowerW: props.currentActivePowerW,
      currentStandbyPowerW: props.currentStandbyPowerW,
      unitName: props.unitName,
      year: props.year,
    },
    $t,
  );
}

function resetState() {
  activeTab.value = 'comment';
  localNote.value = props.note ?? '';
  requestText.value = computeRequestText();
}

function onSaveComment() {
  emit('save', localNote.value.trim());
  emit('update:modelValue', false);
}

function onDeleteComment() {
  emit('delete');
  emit('update:modelValue', false);
}

const feedbackMailtoHref = computed(() => {
  const subject = $t('equipment-power-feedback-email-subject', {
    equipmentName: props.equipmentName,
  });
  return buildMailtoUrl(
    runtimeConfig.equipmentPowerFeedbackEmail,
    subject,
    requestText.value,
  );
});

function onSendRequest() {
  emit('update:modelValue', false);
}
</script>

<style scoped lang="scss">
.feedback-tabs {
  :deep(.q-tabs__arrow) {
    display: none;
  }

  :deep(.q-tab__label) {
    font-weight: 400;
  }

  :deep(.q-tab--active) {
    color: var(--tab-accent);
  }

  :deep(.q-tab__indicator) {
    background: var(--tab-accent);
  }
}
</style>
