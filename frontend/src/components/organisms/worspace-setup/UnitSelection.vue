<script lang="ts" setup>
import Container from 'src/components/atoms/Container.vue';

type Lab = {
  name: string;
  role: string;
  lead: string;
  affiliation: string;
  building: string;
  description: string;
};

defineProps<{
  labs: Lab[];
}>();
</script>

<template>
  <Container>
    <div class="q-gutter-y-sm">
      <h3 class="text-h3">Unit Selection</h3>
      <p class="text-body2 secondary">
        Lorem ipsum dolor sit amet, consectetur adipiscing elit. Quisque ex sem,
        tristique vel felis vitae, dapibus viverra purus. Vestibulum efficitur
        varius sagittis. Vestibulum posuere nunc vel pretium varius. Vivamus
        ultricies leo at lorem eleifend dignissim. Donec gravida turpis nec
        sapien semper finibus. Nulla nibh tortor, vulputate quis erat id,
        pretium scelerisque enim. Suspendisse at posuere ante, mollis aliquet
        turpis.
      </p>
    </div>
  </Container>
</template>
