<script setup lang="ts">
import { ref, onMounted } from 'vue';
import LabSelectorItem from 'src/components/organisms/workspace-selector/LabSelectorItem.vue';
import YearSelector from 'src/components/organisms/workspace-selector/YearSelector.vue';

interface Role {
  role: string;
  on: {
    unit: string;
  };
}

interface UserData {
  id: string;
  sciper: number;
  email: string;
  roles: Role[];
}

const userData = ref<UserData | null>(null);
const selectedLab = ref<string | null>(null);

onMounted(async () => {
  try {
    const response = await fetch('http://localhost:8000/v1/auth/me', {
      credentials: 'include',
    });
    console.log('Response status:', response.status);
    if (response.ok) {
      const data = await response.json();
      userData.value = data;
    } else {
      console.log('Response not OK');
    }
  } catch (error) {
    console.error('Failed to fetch user data:', error);
  }
});
</script>

<template>
  <q-page class="layout-grid">
    <!-- Welcome -->
    <q-card flat class="container">
      <h1 class="text-h2 q-mb-xs">{{ $t('workspace_setup_title') }}</h1>
      <p class="text-body1 q-mb-none">
        {{ $t('workspace_setup_description') }}
      </p>
    </q-card>

    <!-- Lab Selection -->
    <q-card flat class="container">
      <h2 class="text-h3 q-mb-xs">{{ $t('workspace_setup_unit_title') }}</h2>
      <p class="text-body2 text-secondary q-mb-xl">
        {{ $t('workspace_setup_unit_description') }}
      </p>
      <span class="text-h5 text-weight-medium">{{
        $t('workspace_setup_unit_counter', {
          count: userData?.roles?.length ?? 0,
        })
      }}</span>
      <div class="two-column-grid q-mt-sm">
        <LabSelectorItem
          v-for="(roleItem, index) in userData?.roles"
          :key="roleItem.on.unit"
          :selected="selectedLab === roleItem.on.unit"
          :data="{
            id: roleItem.on.unit,
            name: roleItem.on.unit,
            role: roleItem.role,
            years: {},
          }"
          @click="selectedLab = roleItem.on.unit"
        />
      </div>
    </q-card>

    <!-- Year Selection -->
    <q-card flat class="container">
      <h2 class="text-h3 q-mb-xs">{{ $t('workspace_setup_year_title') }}</h2>
      <p class="text-body2 text-secondary q-mb-xl">
        {{ $t('workspace_setup_year_description') }}
      </p>
      <span class="text-h5 text-weight-medium">{{
        $t('workspace_setup_year_counter', {
          count: userData?.roles?.length ?? 0,
        })
      }}</span>
      <YearSelector
        class="q-mt-md"
        :years="[
          {
            year: 2025,
            progress: 100,
            completed_modules: 7,
            comparison: 11.3,
            kgco2: 38450,
            status: 'future',
          },
          {
            year: 2024,
            progress: 43,
            completed_modules: 3,
            comparison: -11.3,
            kgco2: 38450,
            status: 'current',
          },
          {
            year: 2023,
            progress: 100,
            completed_modules: 7,
            comparison: null,
            kgco2: 38450,
            status: 'complete',
          },
        ]"
      />
    </q-card>

    <!-- Confirmation -->
    <q-card flat class="container">
      <h2 class="text-h3">{{ $t('workspace_setup_confirm_selection') }}</h2>
      <div class="two-column-grid q-mt-md">
        <div class="container">
          <h6 class="text-h6 text-weight-medium">
            {{ $t('workspace_setup_confirm_lab') }}
          </h6>
          <h3 class="text-h3 text-weight-medium q-pt-sm">ENAC-IT4R</h3>
          <p class="text-caption">
            Unit Manager: Charlie Weil | ENAC / ENAC-IT
          </p>
        </div>
        <div class="container">
          <h6 class="text-h6 text-weight-medium">
            {{ $t('workspace_setup_confirm_year') }}
          </h6>
          <h3 class="text-h3 text-weight-medium q-pt-sm">2024</h3>
          <p class="text-caption">3/7 | 38,450kg CO2-eq</p>
        </div>
      </div>
      <div class="row q-gutter-sm q-mt-lg justify-end">
        <q-btn
          color="grey-4"
          text-color="primary"
          :label="$t('workspace_setup_restart')"
          unelevated
          no-caps
          outline
          size="md"
          class="text-weight-medium"
        />
        <q-btn
          color="accent"
          :label="$t('workspace_setup_confirm_selection')"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
        />
      </div>
    </q-card>
  </q-page>
</template>

<style lang="scss" scoped>
.two-column-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}
</style>
