# Implementation Plan: Storybook Integration for Component Documentation

## Overview

Integrate Storybook 8.x into the Vue 3 + Quasar application to document and test components. This implementation will create a comprehensive component library similar to the EPFL Elements example, with full support for Quasar framework, custom SCSS architecture, i18n and Pinia stores.

## Requirements

1. Install Storybook 8.x with Vue 3 + Vite support
2. Configure Quasar framework integration (plugins, styles, components)
3. Setup custom decorators for i18n, Pinia, and Vue Router
4. Configure SVG icon plugin in Storybook preview
5. Import SCSS architecture with CSS Cascade Layers
6. Create stories for 6 components (3 atoms + 3 molecules) as a start
7. Create documentation for writing stories

---

## Implementation Steps

### Phase 1: Installation & Configuration (3 files)

#### 1. Install Dependencies

Add to [package.json](frontend/package.json):

**Dev Dependencies:**

```bash
npm install --save-dev \
  @storybook/vue3-vite@^8.4.7 \
  @storybook/addon-essentials@^8.4.7 \
  @storybook/addon-interactions@^8.4.7 \
  @storybook/addon-a11y@^8.4.7 \
  @storybook/addon-links@^8.4.7 \
  @storybook/test@^8.4.7 \
  @storybook/test-runner@^0.21.0 \
  storybook@^8.4.7 \
  concurrently@^9.1.0 \
  wait-on@^8.0.1
```

**NPM Scripts:**

```json
{
  "storybook": "storybook dev -p 6006",
  "storybook:build": "storybook build",
  "storybook:test": "test-storybook",
  "storybook:test-ci": "concurrently -k -s first -n \"SB,TEST\" -c \"magenta,blue\" \"npm run storybook -- --no-open --quiet --ci\" \"wait-on tcp:127.0.0.1:6006 && npm run storybook:test\""
}
```

#### 2. Storybook Main Configuration

**File:** [.storybook/main.ts](frontend/.storybook/main.ts) _(create new)_

- Configure stories glob pattern: `../src/components/**/*.stories.@(js|jsx|mjs|ts|tsx)`
- Register addons: essentials, interactions, a11y, links
- Configure Vite integration with:
  - Path aliases matching Quasar config (src, components, layouts, pages, assets)
  - SCSS preprocessorOptions with additionalData for quasar-bridge
  - Modern compiler API for Sass 1.93.3

#### 3. Storybook Preview Configuration

**File:** [.storybook/preview.ts](frontend/.storybook/preview.ts) _(create new)_

- Import [app.scss](frontend/src/css/app.scss) for CSS Cascade Layers
- Import Quasar icon libraries (Material Icons)
- Setup global app configuration:
  - **Pinia:** Fresh instance per story
  - **Vue I18n:** Composition API with messages from [src/i18n](frontend/src/i18n)
  - **Vue Router:** Memory history with basic routes
  - **Quasar:** Install plugins (Dialog, Loading, Notify)
  - **Icon Plugin:** Register custom SVG icons from [module-icon.ts](frontend/src/plugin/module-icon.ts)
- Configure locale switcher in toolbar (EN/FR)
- Add i18n decorator for global locale switching
- Configure backgrounds and viewport presets

---

### Phase 2: Decorators & Fixtures (4 files)

#### 4. Pinia Store Utilities

**File:** [.storybook/decorators/pinia.ts](frontend/.storybook/decorators/pinia.ts) _(create new)_

- Create `withPinia` decorator for fresh store instances
- Create `withMockStore` helper for overriding initial state
- Prevent state leakage between stories

#### 5. Timeline Mock Data

**File:** [.storybook/fixtures/timeline.ts](frontend/.storybook/fixtures/timeline.ts) _(create new)_

- Export `defaultTimelineState` with module states
- Reference MODULE_STATES and MODULES constants

**File:** [.storybook/fixtures/timelineItems.ts](frontend/.storybook/fixtures/timelineItems.ts) _(create new)_

- Re-export timelineItems from [src/constant/timelineItems](frontend/src/constant/timelineItems.ts)
- Export `mockTimelineItem` for stories

### Phase 3: Atom Stories (3 files)

#### 6. ModuleIcon Stories

**File:** [src/components/atoms/ModuleIcon.stories.ts](frontend/src/components/atoms/ModuleIcon.stories.ts) _(create new)_

- **Stories:** Default, Small, Large, AllIcons, ColorVariants
- **argTypes:** name (select), size (select), color (text)
- **Description:** Custom SVG icon component with size/color variants
- **Features:** Dynamic SVG injection, Vite glob imports

#### 7. CO2Container Stories

**File:** [src/components/atoms/CO2Container.stories.ts](frontend/src/components/atoms/CO2Container.stories.ts) _(create new)_

- **Stories:** Default, WithMultipleElements
- **Description:** Simple slot wrapper with container styling
- **Features:** Single slot, layout styles

#### 8. Co2LanguageSelector Stories

**File:** [src/components/atoms/Co2LanguageSelector.stories.ts](frontend/src/components/atoms/Co2LanguageSelector.stories.ts) _(create new)_

- **Stories:** Default, WithMockRoute
- **Description:** Language switcher using Vue Router
- **Features:** Router-link integration, active state styling

---

### Phase 4: Molecule Stories (3 files)

#### 9. BigNumber Stories

**File:** [src/components/molecules/BigNumber.stories.ts](frontend/src/components/molecules/BigNumber.stories.ts) _(create new)_

- **Stories:** Default, WithComparison, WithColor, WithTooltip, LargeNumber
- **argTypes:** title, number, unit, comparison, comparisonHighlight, color
- **Description:** Q-Card component for displaying large metrics
- **Features:** i18n fallback, slot support, comparison highlighting
- **Interaction Test:** Add play function for tooltip interaction

#### 10. ChartContainer Stories

**File:** [src/components/molecules/ChartContainer.stories.ts](frontend/src/components/molecules/ChartContainer.stories.ts) _(create new)_

- **Stories:** Default, WithTooltip, MultipleCharts
- **argTypes:** title
- **Description:** Q-Card wrapper for charts with title and tooltip
- **Features:** Flat styling, centered content area

#### 11. Co2TimelineItem Stories

**File:** [src/components/molecules/Co2TimelineItem.stories.ts](frontend/src/components/molecules/Co2TimelineItem.stories.ts) _(create new)_

- **Stories:** Default, InProgress, Validated, Selected, AllStates, Timeline
- **argTypes:** currentState (select), selected (boolean)
- **Description:** Timeline navigation item with state indicator
- **Features:** ModuleIcon integration, router navigation, state-based coloring
- **Mock Data:** Use mockTimelineItem from fixtures

---

### Phase 5: Documentation (1 file)

#### 12. Storybook Documentation

**File:** [.storybook/README.md](frontend/.storybook/README.md) _(create new)_

- **Running Storybook:** npm scripts reference
- **Project Structure:** File organization diagram
- **Writing Stories:** Basic story structure, TypeScript types
- **Using i18n:** Locale switching, translation keys
- **Using Pinia:** Store initialization, mock state
- **Using Router:** Memory history, navigation
- **Custom Icons:** SVG icon plugin usage
- **Interaction Testing:** play function examples
- **Best Practices:** Co-location, autodocs, multiple variants
- **Troubleshooting:** Common issues (CSS loading, icons, store state, router errors)

---

### Phase 6: Git Configuration (1 file)

#### 13. Update .gitignore

**File:** [.gitignore](frontend/.gitignore) _(modify)_

Add:

```
# Storybook
storybook-static/
```

---

## Data Flow

### Component Story Rendering

```
User opens Storybook → .storybook/main.ts loads config → .storybook/preview.ts runs setup()
  → Creates Pinia, i18n, router, Quasar → Story file loads → Component renders with args
  → User changes controls → Component re-renders
```

---

## Critical Files (15 total)

### Create (13 files)

1. [.storybook/main.ts](frontend/.storybook/main.ts) - Core configuration
2. [.storybook/preview.ts](frontend/.storybook/preview.ts) - Global setup
3. [.storybook/test-runner.ts](frontend/.storybook/test-runner.ts) - Test config
4. [.storybook/decorators/pinia.ts](frontend/.storybook/decorators/pinia.ts) - Store utilities
5. [.storybook/fixtures/timeline.ts](frontend/.storybook/fixtures/timeline.ts) - Mock data
6. [.storybook/fixtures/timelineItems.ts](frontend/.storybook/fixtures/timelineItems.ts) - Mock data
7. [src/components/atoms/ModuleIcon.stories.ts](frontend/src/components/atoms/ModuleIcon.stories.ts)
8. [src/components/atoms/CO2Container.stories.ts](frontend/src/components/atoms/CO2Container.stories.ts)
9. [src/components/atoms/Co2LanguageSelector.stories.ts](frontend/src/components/atoms/Co2LanguageSelector.stories.ts)
10. [src/components/molecules/BigNumber.stories.ts](frontend/src/components/molecules/BigNumber.stories.ts)
11. [src/components/molecules/ChartContainer.stories.ts](frontend/src/components/molecules/ChartContainer.stories.ts)
12. [src/components/molecules/Co2TimelineItem.stories.ts](frontend/src/components/molecules/Co2TimelineItem.stories.ts)
13. [.storybook/README.md](frontend/.storybook/README.md) - Documentation

### Modify (2 files)

1. [package.json](frontend/package.json) - Add dependencies and scripts
2. [.gitignore](frontend/.gitignore) - Add storybook-static/

---

## Edge Cases

### 1. Quasar CSS Auto-Injection Conflict

- **Issue:** Quasar auto-injects CSS, but app uses manual SCSS with cascade layers
- **Solution:** Import app.scss directly in preview.ts, use SCSS additionalData in main.ts
- **Gotcha:** Ensure app.scss loads before Quasar components

### 2. Vite Glob Import for SVG Icons

- **Issue:** Icon plugin uses import.meta.glob requiring special Vite handling
- **Solution:** Proper alias resolution in main.ts, icons loaded eagerly as raw strings
- **Gotcha:** Icon names must match SVG filenames exactly

### 3. CSS Cascade Layers Specificity

- **Issue:** Layers change CSS specificity, may conflict with Storybook styles
- **Solution:** Full layer structure imported via app.scss
- **Gotcha:** Custom story styles may need higher specificity

### 4. Pinia Store State Persistence

- **Issue:** Stores may persist state between stories
- **Solution:** Fresh Pinia instance per story via preview.ts setup
- **Gotcha:** Disable pinia-plugin-persistedstate in Storybook

### 5. Vue Router Memory History

- **Issue:** Components using useRoute() or router-link need router
- **Solution:** Memory history router in preview.ts with basic routes
- **Gotcha:** Console warnings about missing routes are safe to ignore

### 6. i18n Message Loading

- **Issue:** Messages loaded via Vite glob imports
- **Solution:** Import messages directly in preview.ts
- **Gotcha:** New translation keys require Storybook restart

### 7. TypeScript Path Aliases

- **Issue:** Project uses src/\* aliases from Quasar tsconfig
- **Solution:** Match aliases exactly in main.ts viteFinal()
- **Gotcha:** "Cannot find module" errors indicate alias misconfiguration

---

## Success Criteria

### Functional

✅ Storybook runs on `npm run storybook`
✅ All 6 components have stories with multiple variants
✅ i18n locale switcher works in toolbar
✅ Quasar components render correctly
✅ ModuleIcon displays all SVG icons
✅ CSS Cascade Layers apply correct styling
✅ Pinia stores available in stories
✅ Vue Router works without console errors
✅ Controls addon allows interactive prop editing
✅ Interaction tests run successfully
✅ Test runner executes all stories
✅ Static build produces deployable artifact

### Documentation

✅ .storybook/README.md exists with complete guide
✅ Each story has component description and argTypes
✅ README includes troubleshooting and best practices

---

## Implementation Order

1. **Phase 1:** Install dependencies and create configuration files
2. **Phase 2:** Create decorators and fixtures
3. **Phase 3:** Create atom stories (ModuleIcon → CO2Container → Co2LanguageSelector)
4. **Phase 4:** Create molecule stories (BigNumber → ChartContainer → Co2TimelineItem)
5. **Phase 7:** Create documentation
6. **Phase 8:** Update package.json and .gitignore
7. **Phase 9:** Verify all success criteria
