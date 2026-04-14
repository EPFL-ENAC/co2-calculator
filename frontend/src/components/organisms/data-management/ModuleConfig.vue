<script setup lang="ts">
import { ref, computed } from 'vue';
import { MODULE_CARDS } from 'src/constant/moduleCards';
import {
  MODULES_THRESHOLD_TYPES,
  type ModuleThreshold,
} from 'src/constant/modules';
import { MODULES_CONFIG } from 'src/constant/module-config';
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
const moduleConfig = computed(() => MODULES_CONFIG[selected.value.module]);
const submodules = computed(() => moduleConfig.value?.submodules ?? []);

const expanded = ref(false);
const moduleActive = ref(true);
const uncertainty = ref<'none' | 'low' | 'medium' | 'high'>('none');
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

      <!-- Activate Module -->
      <q-separator />
      <q-card flat class="q-pa-none row items-center">
        <q-card flat class="col q-px-lg q-pt-lg q-pb-md">
          <div class="row items-center q-mb-xs">
            <q-icon name="o_power" color="accent" size="sm" class="q-mr-sm" />
            <div class="text-body1 text-weight-medium">
              {{ $t('data_management_module_activation_title') }}
            </div>
          </div>
          <div class="text-body2 text-secondary">
            {{ $t('data_management_module_activation_description') }}
          </div>
        </q-card>
        <q-toggle
          v-model="moduleActive"
          color="accent"
          keep-color
          size="lg"
          class="q-pr-lg"
        />
      </q-card>

      <!-- Threshold -->
      <q-separator class="q-my-xs" />
      <q-card flat class="q-px-lg q-pt-lg q-pb-md">
        <div class="row items-center q-mb-xs">
          <q-icon name="o_tune" color="accent" size="sm" class="q-mr-sm" />
          <div class="text-body1 text-weight-medium">
            {{ $t('data_management_threshold_title') }}
          </div>
        </div>
        <div class="text-body2 text-secondary q-mb-md">
          {{ $t('data_management_threshold_description') }}
        </div>
        <div class="row">
          <div
            v-for="type in MODULES_THRESHOLD_TYPES"
            :key="type"
            class="col-xs-12 col-lg-4 q-pr-md q-pb-sm"
          >
            <module-threshold-input v-model="selected" :type="type" />
          </div>
        </div>
      </q-card>

      <!-- Submodules -->
      <template v-if="submodules.length > 0">
        <q-separator class="q-my-xs" />
        <q-card flat class="q-px-lg q-pt-lg q-pb-md">
          <div class="row items-center q-mb-md">
            <q-icon
              name="o_view_cozy"
              color="accent"
              size="sm"
              class="q-mr-sm"
            />
            <div class="text-body1 text-weight-medium">
              {{ $t('data_management_submodules_configuration_title') }}
            </div>
          </div>

          <template v-for="submodule in submodules" :key="submodule.id">
            <q-card flat bordered class="q-mb-md q-pa-none">
              <!-- Submodule header -->
              <div
                class="q-px-md q-pt-md q-pb-sm text-body2 text-weight-medium"
              >
                {{
                  submodule.tableNameKey
                    ? $t(submodule.tableNameKey)
                    : submodule.id
                }}
              </div>
              <q-separator />
              <!-- Data / Factors columns -->
              <div class="row">
                <!-- Data column -->
                <q-card flat class="col q-pa-md border-right">
                  <div class="row items-center q-mb-xs">
                    <q-icon
                      name="o_storage"
                      color="accent"
                      size="xs"
                      class="q-mr-xs"
                    />
                    <div class="text-body2 text-weight-medium">
                      {{ $t('data_management_data') }}
                    </div>
                  </div>
                  <div class="text-caption text-secondary q-mb-sm">
                    {{
                      $t('data_management_submodules_configuration_description')
                    }}
                  </div>
                  <q-btn
                    icon="o_add"
                    color="primary"
                    outline
                    size="sm"
                    :label="$t('data_management_add_data')"
                    class="text-weight-medium text-capitalize"
                  />
                </q-card>

                <!-- Factors column -->
                <q-card flat class="col q-pa-md border-right">
                  <div class="row items-center q-mb-xs">
                    <q-icon
                      name="o_settings"
                      color="accent"
                      size="xs"
                      class="q-mr-xs"
                    />
                    <div class="text-body2 text-weight-medium">
                      {{ $t('data_management_factor') }}
                    </div>
                    <q-space />
                    <span class="text-caption text-negative"
                      >*{{ $t('common_mandatory') }}</span
                    >
                  </div>
                  <div class="text-caption text-secondary q-mb-sm">
                    {{ $t('data_management_description') }}
                  </div>
                  <q-btn
                    icon="o_add"
                    color="accent"
                    size="sm"
                    :label="$t('data_management_add_factors')"
                    class="text-weight-medium text-capitalize"
                  />
                </q-card>
              </div>
            </q-card>
          </template>
        </q-card>
      </template>

      <!-- Uncertainty -->
      <q-separator class="q-my-xs" />
      <q-card flat class="q-px-lg q-pt-lg q-pb-md">
        <div class="row items-center q-mb-xs">
          <q-icon
            name="o_help_center"
            color="accent"
            size="sm"
            class="q-mr-sm"
          />
          <div class="text-body1 text-weight-medium">
            {{ $t('data_management_uncertainty_title') }}
          </div>
        </div>
        <div class="text-body2 text-secondary q-mb-sm">
          {{ $t('data_management_uncertainty_description') }}
        </div>
        <div class="row q-gutter-md">
          <q-radio
            v-model="uncertainty"
            val="none"
            :label="$t('data_management_uncertainty_none')"
            color="accent"
          />
          <q-radio
            v-model="uncertainty"
            val="low"
            :label="$t('data_management_uncertainty_low')"
            color="accent"
          />
          <q-radio
            v-model="uncertainty"
            val="medium"
            :label="$t('data_management_uncertainty_medium')"
            color="accent"
          />
          <q-radio
            v-model="uncertainty"
            val="high"
            :label="$t('data_management_uncertainty_high')"
            color="accent"
          />
        </div>
      </q-card>
    </q-expansion-item>
  </q-card>
</template>
