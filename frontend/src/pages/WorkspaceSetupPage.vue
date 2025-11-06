<script setup lang="ts">
import { ref, onMounted } from 'vue';
import Container from 'src/components/atoms/Container.vue';
import UnitSelection from 'src/components/organisms/worspace-setup/UnitSelection.vue';

const labs = ref([]);
const recordedYears = ref([]);

const getLabs = async () => {
  const response = await fetch('/mock/api/workspace-setup.json');
  const data = await response.json();
  labs.value = data.labs;
  recordedYears.value = data.recordedYears;
};

onMounted(() => {
  getLabs();
});
</script>

<template>
  <q-page-container>
    <q-page class="q-gutter-y-xl q-my-xl">
      <Container>
        <div class="q-gutter-y-sm">
          <h2 class="text-h2">{{ $t('workspace_setup_title') }}</h2>
          <p class="text-body1">{{ $t('workspace_setup_description') }}</p>
        </div>
      </Container>
      <UnitSelection v-if="labs.length > 1" :labs="labs" />
    </q-page>
  </q-page-container>
</template>
