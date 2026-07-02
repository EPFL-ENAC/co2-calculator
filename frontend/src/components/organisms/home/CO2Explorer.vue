<script setup lang="ts"></script>

<template>
  <section class="co2-explorer">
    <div class="row items-start justify-between no-wrap q-mb-md">
      <div class="row items-center q-gutter-sm">
        <q-icon name="o_explore" size="md" color="info" />
        <h2 class="text-h3 q-mb-none">{{ $t('co2_explorer_title') }}</h2>
      </div>
      <q-btn
        color="info"
        :label="$t('co2_explorer_btn')"
        icon="o_add"
        unelevated
        no-caps
        size="md"
        class="text-weight-medium"
        :to="{ name: 'simulation-explore', params: { explore: 'new' } }"
      />
    </div>

    <p class="text-body1 section-intro q-mb-none">
      {{ $t('co2_explorer_description') }}
    </p>
  </section>
</template>

<style scoped lang="scss">
// Intro/description text under a section title is capped at three-quarters width.
.section-intro {
  max-width: 75%;
}
</style>
