# Implementation Plan: Storybook Integration for Component Documentation

## Overview

Integrate Storybook 10.1.x into the Vue 3 + Quasar application to document and test components. This implementation will create a comprehensive component library similar to the EPFL Elements example, with full support for Quasar framework, custom SCSS architecture, i18n and Pinia stores.

## Architecture

Storybook will be organized within the `frontend/` directory with the following structure:

```
frontend/
├── src/
│   └── components/
│       └── **/*.stories.ts  (co-located with components)
├── storybook/
│   ├── .storybook/          (Storybook configuration)
│   └── stories/             (additional stories if needed)
├── Dockerfile               (existing frontend app)
└── Dockerfile.storybook     (Storybook Docker image)
```

The CI/CD pipeline will build both Docker images: the main frontend app and the Storybook static site.

## Requirements

1. Install Storybook 10.1.x with Vue 3 + Vite support
2. Configure Quasar framework integration (plugins, styles, components)
3. Setup custom decorators for i18n, Pinia, and Vue Router
4. Configure SVG icon plugin in Storybook preview
5. Import SCSS architecture with CSS Cascade Layers
6. Create stories for components across atoms, molecules, charts, and layout categories
7. Create documentation for writing stories
8. Create Dockerfile.storybook for containerized Storybook deployment
9. Update CI/CD pipeline to build Storybook Docker image
10. Add Storybook command line helpers to frontend Makefile

---

## Implementation Steps

### Phase 1: Installation & Configuration (3 files)

#### 1. Install Dependencies

Add to [package.json](frontend/package.json):

**Dev Dependencies:**

```bash
npm install --save-dev \
  @storybook/vue3-vite@^10.1.8 \
  @storybook/addon-a11y@^10.1.8 \
  @storybook/test@^10.1.8 \
  @storybook/test-runner@^0.24.2 \
  storybook@^10.1.8 \
  concurrently@^9.2.1 \
  wait-on@^9.0.1
```

**Note:** In Storybook 10.x, `@storybook/addon-essentials`, `@storybook/addon-interactions`, and `@storybook/addon-links` have been deprecated and integrated into Storybook's core. They should not be installed as separate packages.

**NPM Scripts:**

```json
{
  "storybook": "storybook dev -p 6006",
  "storybook:build": "storybook build",
  "storybook:test": "test-storybook",
  "storybook:test-ci": "concurrently -k -s first -n \"SB,TEST\" -c \"magenta,blue\" \"npm run storybook -- --no-open --quiet --ci\" \"wait-on tcp:127.0.0.1:6006 && npm run storybook:test\""
}
```

**Note:** All Storybook commands are run from the `frontend/` directory. Storybook will automatically detect the configuration in `storybook/.storybook/` directory.

#### 2. Storybook Main Configuration

**File:** [storybook/.storybook/main.ts](frontend/storybook/.storybook/main.ts) _(create new)_

- Configure stories glob pattern: `../../src/components/**/*.stories.@(js|jsx|mjs|ts|tsx)`
- Configure optional stories directory: `../stories/**/*.stories.@(js|jsx|mjs|ts|tsx)` (for additional standalone stories)
- Set `stories` array in StorybookConfig to include both patterns
- Register addons: `@storybook/addon-a11y` (essentials, interactions, and links are now built into Storybook core)
- Configure Vite integration with:
  - Path aliases matching Quasar config (src, components, layouts, pages, assets)
  - SCSS preprocessorOptions with additionalData for quasar-bridge
  - Modern compiler API for Sass 1.93.3

#### 3. Storybook Preview Configuration

**File:** [storybook/.storybook/preview.ts](frontend/storybook/.storybook/preview.ts) _(create new)_

- Import [../../src/css/app.scss](frontend/src/css/app.scss) for CSS Cascade Layers
- Import Quasar icon libraries (Material Icons)
- Setup global app configuration:
  - **Pinia:** Fresh instance per story
  - **Vue I18n:** Composition API with messages from [../../src/i18n](frontend/src/i18n)
  - **Vue Router:** Memory history with basic routes
  - **Quasar:** Install plugins (Dialog, Loading, Notify)
  - **Icon Plugin:** Register custom SVG icons from [../../src/plugin/module-icon.ts](frontend/src/plugin/module-icon.ts)
- Configure locale switcher in toolbar (EN/FR)
- Add i18n decorator for global locale switching
- Configure backgrounds and viewport presets

---

### Phase 2: Decorators & Fixtures (4 files)

#### 4. Pinia Store Utilities

**File:** [storybook/.storybook/decorators/pinia.ts](frontend/storybook/.storybook/decorators/pinia.ts) _(create new)_

- Create `withPinia` decorator for fresh store instances
- Create `withMockStore` helper for overriding initial state
- Prevent state leakage between stories

#### 5. Timeline Mock Data

**File:** [storybook/.storybook/fixtures/timeline.ts](frontend/storybook/.storybook/fixtures/timeline.ts) _(create new)_

- Export `defaultTimelineState` with module states
- Reference MODULE_STATES and MODULES constants from `../../src`

**File:** [storybook/.storybook/fixtures/timelineItems.ts](frontend/storybook/.storybook/fixtures/timelineItems.ts) _(create new)_

- Re-export timelineItems from [../../src/constant/timelineItems](frontend/src/constant/timelineItems.ts)
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

### Phase 4b: Chart Stories (1 file for now)

#### 12. Chart Component Stories

**Files:** Create stories for chart components in `src/components/charts/results/` _(create new)_

- **Components to document:**
  - `ModuleCarbonFootprintChart.stories.ts`

- **Stories pattern:** Default, WithData, WithLoading, WithEmptyState
- **argTypes:** data, loading, error states
- **Description:** ECharts-based visualization components
- **Features:** ECharts integration, data transformations, responsive sizing
- **Mock Data:** Create chart data fixtures for different scenarios

**Note:** During implementation, determine if charts should remain a separate category or be consolidated into molecules.

---

### Phase 4c: Layout Stories (2 files)

#### 13. Layout Component Stories

**File:** [src/components/layout/Co2Header.stories.ts](frontend/src/components/layout/Co2Header.stories.ts) _(create new)_

- **Stories:** Default, WithNavigation, WithUser, MobileView
- **Description:** Main application header component
- **Features:** Navigation links, user menu, responsive layout

**File:** [src/components/layout/Co2Sidebar.stories.ts](frontend/src/components/layout/Co2Sidebar.stories.ts) _(create new)_

- **Stories:** Default, Collapsed, WithActiveRoute, MobileView
- **Description:** Application sidebar navigation
- **Features:** Route highlighting, collapse state, mobile responsiveness

---

### Phase 5: Component Architecture Review (documentation task)

#### 14. Review Organisms Category

**Task:** During Storybook implementation, review the `organisms/` directory .

- **Create a review document:** `storybook/.storybook/ARCHITECTURE_REVIEW.md`
- **Evaluate each organism component:**
  - Should it be in molecules instead?
  - Should it be in layouts?
  - Should it be split into smaller components?
  - Is the current categorization appropriate?

---

### Phase 6: Documentation (1 file)

#### 15. Storybook Documentation

**File:** [storybook/.storybook/README.md](frontend/storybook/.storybook/README.md) _(create new)_

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

### Phase 7: Docker Configuration (1 file)

#### 16. Create Dockerfile.storybook

**File:** [Dockerfile.storybook](frontend/Dockerfile.storybook) _(create new)_

- Multi-stage build similar to main Dockerfile
- Use `node:24-alpine` as builder
- Run `npm run storybook:build` to generate static site
- Use `nginx:stable-alpine-slim` for production
- Copy built files from `storybook-static/` to nginx html directory
- Expose port 8080 (or 6006 for consistency)
- Include healthcheck

**Example structure:**

```dockerfile
FROM node:24-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run storybook:build

FROM nginx:stable-alpine-slim
COPY --from=builder /app/storybook-static /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
```

---

### Phase 8: CI/CD Integration (modify existing workflow)

#### 17. Update CI/CD Pipeline

**File:** [.github/workflows/deploy.yml](.github/workflows/deploy.yml) _(modify)_

- Update `build_context` to include Storybook Docker build
- Add Storybook image build step
- Ensure `Dockerfile.storybook` is built alongside main frontend Dockerfile
- Tag Storybook image appropriately (e.g., `-storybook` suffix)

**Note:** The `epfl-enac-build-push-deploy-action` may need to be configured to recognize `Dockerfile.storybook` or a separate workflow step may be needed.

---

### Phase 9: Makefile Helpers (modify existing)

#### 18. Add Storybook Commands to Makefile

**File:** [Makefile](frontend/Makefile) _(modify)_

Add the following commands:

```makefile
.PHONY: storybook
storybook: ## Start Storybook development server
	npm run storybook

.PHONY: storybook-build
storybook-build: ## Build Storybook static site
	npm run storybook:build

.PHONY: storybook-test
storybook-test: ## Run Storybook interaction tests
	npm run storybook:test

.PHONY: storybook-docker-build
storybook-docker-build: ## Build Storybook Docker image
	docker build -f Dockerfile.storybook -t co2-calculator-storybook .

.PHONY: storybook-docker-run
storybook-docker-run: ## Run Storybook Docker container
	docker run -p 8080:8080 co2-calculator-storybook
```

---

### Phase 10: Git Configuration (1 file)

#### 19. Update .gitignore

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
User opens Storybook → storybook/.storybook/main.ts loads config → storybook/.storybook/preview.ts runs setup()
  → Creates Pinia, i18n, router, Quasar → Story file loads from src/components/**/*.stories.ts
  → Component renders with args → User changes controls → Component re-renders
```

### Docker Build Flow

```
CI/CD Pipeline → Build frontend Dockerfile (main app)
              → Build Dockerfile.storybook (static Storybook site)
              → Push both images to registry
              → Deploy both services (optional)
```

---

## Critical Files (18-20 total)

### Create (15-17 story files + config)

**Configuration Files:**

1. [storybook/.storybook/main.ts](frontend/storybook/.storybook/main.ts) - Core configuration
2. [storybook/.storybook/preview.ts](frontend/storybook/.storybook/preview.ts) - Global setup
3. [storybook/.storybook/test-runner.ts](frontend/storybook/.storybook/test-runner.ts) - Test config
4. [storybook/.storybook/decorators/pinia.ts](frontend/storybook/.storybook/decorators/pinia.ts) - Store utilities
5. [storybook/.storybook/fixtures/timeline.ts](frontend/storybook/.storybook/fixtures/timeline.ts) - Mock data
6. [storybook/.storybook/fixtures/timelineItems.ts](frontend/storybook/.storybook/fixtures/timelineItems.ts) - Mock data

**Atom Stories:** 7. [src/components/atoms/ModuleIcon.stories.ts](frontend/src/components/atoms/ModuleIcon.stories.ts) 8. [src/components/atoms/CO2Container.stories.ts](frontend/src/components/atoms/CO2Container.stories.ts) 9. [src/components/atoms/Co2LanguageSelector.stories.ts](frontend/src/components/atoms/Co2LanguageSelector.stories.ts)

**Molecule Stories:** 10. [src/components/molecules/BigNumber.stories.ts](frontend/src/components/molecules/BigNumber.stories.ts) 11. [src/components/molecules/ChartContainer.stories.ts](frontend/src/components/molecules/ChartContainer.stories.ts) 12. [src/components/molecules/Co2TimelineItem.stories.ts](frontend/src/components/molecules/Co2TimelineItem.stories.ts)

**Chart Stories (to be determined during implementation):** 13. [src/components/charts/results/ModuleCarbonFootprintChart.stories.ts](frontend/src/components/charts/results/ModuleCarbonFootprintChart.stories.ts) _(required)_ 14. Additional chart stories as needed (optional)

**Layout Stories:** 15. [src/components/layout/Co2Header.stories.ts](frontend/src/components/layout/Co2Header.stories.ts) 16. [src/components/layout/Co2Sidebar.stories.ts](frontend/src/components/layout/Co2Sidebar.stories.ts)

**Documentation:** 17. [storybook/.storybook/README.md](frontend/storybook/.storybook/README.md) - User documentation 18. [storybook/.storybook/ARCHITECTURE_REVIEW.md](frontend/storybook/.storybook/ARCHITECTURE_REVIEW.md) - Architecture review findings

**Docker:** 19. [Dockerfile.storybook](frontend/Dockerfile.storybook) - Storybook Docker image

### Modify (3 files)

1. [package.json](frontend/package.json) - Add dependencies and scripts
2. [.gitignore](frontend/.gitignore) - Add storybook-static/
3. [Makefile](frontend/Makefile) - Add Storybook command helpers
4. [.github/workflows/deploy.yml](.github/workflows/deploy.yml) - Add Storybook Docker build (or separate workflow)

---

## Architecture Decisions (To Be Determined During Implementation)

### 1. Charts Category Structure

**Question:** Should `charts/` remain a separate category or be consolidated into `molecules/`?

**Considerations:**

- **Keep separate if:**
  - Charts have distinct complexity/patterns (ECharts integration, data transformations)
  - Charts are domain-specific (results charts vs general charts)
  - Team prefers clear separation of visualization components

- **Consolidate into molecules if:**
  - Charts are essentially complex molecules (composed of atoms, reusable)
  - No significant architectural difference from other molecule components
  - Simplifies navigation and reduces category overhead

## **Default recommendation:** Start by documenting charts as separate category. Revisit after creating initial stories to assess if consolidation makes sense.

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

✅ Storybook runs on `npm run storybook` or `make storybook`
✅ Storybook Docker image builds successfully with `make storybook-docker-build`
✅ CI/CD pipeline builds Storybook Docker image
✅ Storybook static site is served correctly in Docker container
✅ All component categories have stories (atoms, molecules, charts, layout)
✅ Components have multiple story variants demonstrating different states and use cases
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

✅ storybook/.storybook/README.md exists with complete guide
✅ Each story has component description and argTypes
✅ README includes troubleshooting and best practices

---

## Implementation Order

1. **Phase 1:** Install dependencies and create configuration files
2. **Phase 2:** Create decorators and fixtures
3. **Phase 3:** Create atom stories (ModuleIcon → CO2Container → Co2LanguageSelector)
4. **Phase 4:** Create molecule stories (BigNumber → ChartContainer → Co2TimelineItem)
5. **Phase 4b:** Create chart stories (ModuleCarbonFootprintChart, others as needed)
   - **Decision point:** Determine if charts category should remain separate or be consolidated into molecules
6. **Phase 4c:** Create layout stories (Co2Header → Co2Sidebar)
7. **Phase 5:** Review organisms architecture and document findings (parallel to story creation)
8. **Phase 6:** Create documentation (README.md and ARCHITECTURE_REVIEW.md)
9. **Phase 7:** Create Dockerfile.storybook
10. **Phase 8:** Update CI/CD pipeline for Storybook build
11. **Phase 9:** Add Makefile helpers for Storybook commands
12. **Phase 10:** Update .gitignore
13. **Phase 11:** Verify all success criteria
