# ADR-002: Use Vue 3 + Quasar for Frontend

**Status**: Accepted  
**Date**: 2024-11-20  
**Deciders**: Development Team, Product Owner

## TL;DR

Use Vue 3 with Composition API and Quasar Framework for rapid
development, excellent i18n support, and team productivity.

## Context

We need a modern frontend framework for a multi-language web app
with data visualization, responsive design, and fast iteration.
We evaluated React and Vue 3 based on team experience, bundle
size, development speed, and ecosystem maturity.

## Decision

**Use Vue 3 + Quasar** as the frontend stack.

**Why Vue 3 wins:**

- Team has prior Vue experience
- Single-file components enable faster development
- Easier onboarding for new developers
- Smaller bundle size (~20% lighter than React)
- Composition API provides modern reactive model
- Quasar provides ready-made components, i18n, and PWA support

## Alternatives Considered

**React + Next.js/Material-UI**

Pros:

- Largest ecosystem with more third-party libraries
- Strong TypeScript support

Cons:

- Steeper learning curve
- More boilerplate code
- Larger bundles
- Team less familiar with React patterns

| Criterion         | Vue 3 + Quasar | React      |
| ----------------- | -------------- | ---------- |
| Team Experience   | ✅ High        | ⚠️ Medium  |
| Learning Curve    | ✅ Gentle      | ⚠️ Steep   |
| Development Speed | ✅ Fast        | ⚠️ Medium  |
| Bundle Size       | ✅ Smaller     | ⚠️ Larger  |
| Ecosystem         | ⚠️ Large       | ✅ Largest |

## Consequences

**Positive:**

- Faster development with single-file components
- Quasar provides comprehensive UI library, i18n, and PWA support
- Better developer experience with DevTools and HMR
- Smaller bundle sizes improve load times
- TypeScript support throughout the stack
- Leverage team's existing Vue framework knowledge
- CSS token system in place and easy to theme

**Negative:**

- Smaller ecosystem compared to React
- React developers more common in hiring market
- Quasar is Vue-specific, creating framework lock-in

**Mitigation:**

- Vue is learnable for React developers in ~2 weeks
- API client (ky) is framework-agnostic and portable
- Business logic in Pinia stores can be extracted if needed

## Implementation

**Stack:**

- Vue 3 (Composition API) + Vue Router 4
- Quasar 2 (UI components)
- Pinia 2+ (state management)
- Vite 5+ (build tool)
- ky (HTTP client)
- Playwright (E2E testing)

**Example component:**

```vue
<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();
const count = ref(0);
</script>

<template>
  <q-card>
    <q-card-section>{{ t("greeting") }}: {{ count }}</q-card-section>
  </q-card>
</template>
```

## References

- [Vue 3 Documentation](https://vuejs.org/)
- [Quasar Framework](https://quasar.dev/)
- [Pinia State Management](https://pinia.vuejs.org/)
