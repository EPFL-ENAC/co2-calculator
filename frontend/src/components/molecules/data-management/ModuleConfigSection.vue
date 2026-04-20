<script setup lang="ts">
import { useModuleConfig } from 'src/composables/useModuleConfig';
import { useI18n } from 'vue-i18n';

interface Props {
  module: string;
}

const props = defineProps<Props>();
const { t: $t } = useI18n();

const {
  isModuleEnabled,
  getModuleUncertainty,
  updateModuleEnabled,
  updateModuleUncertainty,
} = useModuleConfig({
  module: props.module,
  selectedYear: 2024,
});
</script>

<template>
  <q-card flat class="q-pa-none row">
    <q-card flat class="col q-px-lg q-pt-xl q-pb-md border-right">
      <div class="row items-center q-mb-xs">
        <q-icon
          name="power_settings_new"
          color="accent"
          size="xs"
          class="q-mr-sm"
        />
        <div class="text-body1 text-weight-medium">
          {{ $t('data_management_module_activation_title') }}
        </div>
      </div>
      <div class="text-body2 text-secondary q-mb-sm">
        {{ $t('data_management_module_activation_description') }}
      </div>
      <q-toggle
        :model-value="isModuleEnabled(props.module)"
        color="accent"
        keep-color
        size="lg"
        @update:model-value="
          (val: boolean) => updateModuleEnabled(props.module, val)
        "
      />
    </q-card>
  </q-card>

  <q-separator class="q-my-xs" />

  <q-card flat class="q-pa-none row">
    <q-card flat class="col q-px-lg q-pt-xl q-pb-md border-right">
      <div class="row items-center q-mb-xs">
        <q-icon name="o_help_center" color="accent" size="xs" class="q-mr-sm" />
        <div class="text-body1 text-weight-medium">
          {{ $t('data_management_uncertainty_title') }}
        </div>
      </div>
      <div class="text-body2 text-secondary q-mb-sm">
        {{ $t('data_management_uncertainty_description') }}
      </div>
      <q-radio
        :model-value="getModuleUncertainty(props.module)"
        val="none"
        :label="$t('data_management_uncertainty_none')"
        color="accent"
        @update:model-value="updateModuleUncertainty(props.module, 'none')"
      />
      <q-radio
        :model-value="getModuleUncertainty(props.module)"
        val="low"
        :label="$t('data_management_uncertainty_low')"
        color="accent"
        @update:model-value="updateModuleUncertainty(props.module, 'low')"
      />
      <q-radio
        :model-value="getModuleUncertainty(props.module)"
        val="medium"
        :label="$t('data_management_uncertainty_medium')"
        color="accent"
        @update:model-value="updateModuleUncertainty(props.module, 'medium')"
      />
      <q-radio
        :model-value="getModuleUncertainty(props.module)"
        val="high"
        :label="$t('data_management_uncertainty_high')"
        color="accent"
        @update:model-value="updateModuleUncertainty(props.module, 'high')"
      />
    </q-card>
  </q-card>
</template>

<style scoped>
.border-right {
  border-right: 1px solid rgba(0, 0, 0, 0.12);
}
</style>
