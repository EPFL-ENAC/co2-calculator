<script setup lang="ts">
import { ref, computed } from 'vue';
import { MODULE_CARDS } from 'src/constant/moduleCards';
import {
  MODULES_THRESHOLD_TYPES,
  type ModuleThreshold,
} from 'src/constant/modules';
import ModuleThresholdInput from 'src/components/organisms/data-management/ModuleThresholdInput.vue';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';

const props = defineProps<{
  modelValue: ModuleThreshold;
  year: number;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: ModuleThreshold): void;
}>();

const selected = computed({
  get: () => props.modelValue,
  set: (val: ModuleThreshold) => {
    emit('update:modelValue', val);
  },
});
const card = computed(() =>
  MODULE_CARDS.find((c) => c.module === selected.value.module),
);
const expanded = ref(false);
</script>

<template>
  <q-card v-if="card" flat bordered class="q-pa-none">
    <q-expansion-item v-model="expanded" expand-separator>
      <template #header>
        <q-item-section avatar>
          <module-icon :name="card.module" size="md" color="accent" />
        </q-item-section>
        <q-item-section class="text-h4 text-weight-medium">
          {{ $t(card.module) }}
        </q-item-section>
        <q-item-section v-if="!expanded" class="text-caption text-grey-6">
          {{
            $t(`threshold_${selected.threshold.type}_summary`, {
              value: selected.threshold.value ?? '??',
            })
          }}
        </q-item-section>
      </template>
      <q-card>
        <q-card-section>
          <div class="row">
            <div
              v-for="type in MODULES_THRESHOLD_TYPES"
              :key="type"
              class="col-xs-12 col-lg-4 q-pa-md"
            >
              <module-threshold-input v-model="selected" :type="type" />
            </div>
          </div>
        </q-card-section>
      </q-card>
    </q-expansion-item>
  </q-card>
</template>
