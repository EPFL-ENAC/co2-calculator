<script setup lang="ts">
import { computed } from 'vue';
import { MODULE_CARDS } from 'src/constant/moduleCards';
import ModuleIcon from 'src/components/atoms/ModuleIcon.vue';
import { useI18n } from 'vue-i18n';
import { type ModuleConfig } from 'src/stores/yearConfig';

interface Props {
  module: string;
  year: number;
  expanded: boolean;
}

const props = defineProps<Props>();

const emit = defineEmits<{
  (e: 'update:expanded', value: boolean): void;
  (e: 'save', value: ModuleConfig): void;
}>();

const { t: $t } = useI18n();

const card = computed(() =>
  MODULE_CARDS.find((c) => c.module === props.module),
);

const localConfig = defineModel<ModuleConfig>('config', {
  default: {
    enabled: true,
    uncertainty_tag: 'medium',
    submodules: {},
  },
});

const emitExpanded = (value: boolean) => {
  emit('update:expanded', value);
};

const handleSave = () => {
  emit('save', { ...localConfig.value });
};
</script>

<template>
  <q-card flat bordered class="q-pa-none">
    <q-expansion-item
      :model-value="expanded"
      expand-separator
      @update:model-value="emitExpanded"
    >
      <template #header>
        <q-item-section avatar>
          <module-icon
            :name="card?.module || module"
            size="md"
            color="accent"
          />
        </q-item-section>
        <q-item-section class="text-h4 text-weight-medium">
          {{ $t(module) }}
        </q-item-section>
        <q-item-section v-if="!expanded" class="text-caption text-grey-6">
          {{ $t(`uncertainty_${localConfig.uncertainty_tag}`) }}
        </q-item-section>
      </template>

      <q-card>
        <q-card-section>
          <!-- Module-level settings -->
          <div class="row q-gutter-md q-mb-md">
            <!-- Enable/Disable toggle -->
            <q-toggle
              v-model="localConfig.enabled"
              :label="$t('module_enabled')"
              color="primary"
            />

            <!-- Uncertainty level -->
            <q-select
              v-model="localConfig.uncertainty_tag"
              :options="[
                { label: $t('uncertainty_low'), value: 'low' },
                { label: $t('uncertainty_medium'), value: 'medium' },
                { label: $t('uncertainty_high'), value: 'high' },
                { label: $t('uncertainty_none'), value: 'none' },
              ]"
              :label="$t('uncertainty_level')"
              outlined
              dense
              emit-value
              map-options
              class="q-mt-md"
              style="width: 250px"
            />
          </div>

          <!-- Submodules table -->
          <div v-if="Object.keys(localConfig.submodules).length > 0">
            <div class="text-subtitle2 q-mb-sm">{{ $t('submodules') }}</div>

            <q-table
              :rows="
                Object.entries(localConfig.submodules).map(
                  ([key, value]: [string, any]) => ({
                    id: key,
                    ...value,
                  }),
                )
              "
              :columns="[
                {
                  name: 'enabled',
                  label: $t('enabled'),
                  field: 'enabled',
                  align: 'center',
                  headerStyle: 'width: 100px',
                },
                {
                  name: 'threshold',
                  label: $t('threshold_kg_co2eq'),
                  field: 'threshold',
                  align: 'right',
                },
              ]"
              flat
              dense
              :pagination="{ rowsPerPage: 10 }"
              hide-bottom
            >
              <template #body="rowProps">
                <q-tr :props="rowProps">
                  <q-td
                    key="enabled"
                    :props="rowProps"
                    style="text-align: center"
                  >
                    <q-toggle
                      v-model="(rowProps.row as any).enabled"
                      color="primary"
                      @update:model-value="handleSave"
                    />
                  </q-td>
                  <q-td key="threshold" :props="rowProps">
                    <q-input
                      v-model.number="(rowProps.row as any).threshold"
                      type="number"
                      dense
                      outlined
                      :debounce="600"
                      :placeholder="$t('no_threshold')"
                      @update:model-value="handleSave"
                    >
                      <template #append>
                        <span class="text-caption text-grey">kg</span>
                      </template>
                    </q-input>
                  </q-td>
                </q-tr>
              </template>
            </q-table>
          </div>
          <div v-else class="text-caption text-grey-6">
            {{ $t('no_submodules_configured') }}
          </div>
        </q-card-section>
      </q-card>
    </q-expansion-item>
  </q-card>
</template>
