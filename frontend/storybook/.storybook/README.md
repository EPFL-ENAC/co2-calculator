# Storybook Configuration

This directory contains the Storybook configuration for the CO2 Calculator frontend application. Storybook is used for component development, documentation, and visual testing.

## Overview

The Storybook setup is configured to work with:

- **Vue 3** with Vite
- **Quasar** UI framework
- **Pinia** for state management
- **Vue Router** for routing
- **Vue i18n** for internationalization
- **SCSS** for styling

## Configuration Files

- **`main.ts`**: Main Storybook configuration including stories paths, addons, and Vite customization
- **`preview.ts`**: Global decorators, parameters, and Vue app setup (Quasar, Pinia, i18n, Router)
- **`decorators/pinia.ts`**: Pinia-specific decorators for managing store state in stories

## Usage Instructions

### Running Storybook Locally

Start the Storybook development server:

```bash
# Using Make (recommended)
make storybook

# Or using npm directly
npm run storybook
```

This will start Storybook on `http://localhost:6006` with hot module reloading.

### Building Storybook

Build a static version of Storybook for deployment:

```bash
# Using Make (recommended)
make storybook-build

# Or using npm directly
npm run storybook:build
```

The static files will be generated in the `storybook-static/` directory at the project root.

### Testing Stories

Run Storybook's test runner to verify all stories render correctly:

```bash
# Using Make (recommended)
make storybook-test

# Or using npm directly
npm run storybook:test
```

For CI environments, use:

```bash
# Using Make (recommended)
make storybook-test-ci

# Or using npm directly
npm run storybook:test-ci
```

This command starts Storybook in CI mode and runs tests once it's ready.

### Running Storybook in Docker

Build and run Storybook using Docker:

```bash
# Using Make (recommended)
make storybook-docker

# Or using docker directly
docker build -f Dockerfile.storybook -t storybook .
docker run -p 8080:8080 storybook
```

The Storybook site will be available at `http://localhost:8080`.

## Writing Stories

### Story File Location

Stories can be placed in two locations:

1. **Component directory**: `src/components/**/*.stories.@(js|jsx|mjs|ts|tsx)`
2. **Storybook stories directory**: `storybook/stories/**/*.stories.@(js|jsx|mjs|ts|tsx)`

### Basic Story Structure

```typescript
import type { Meta, StoryObj } from '@storybook/vue3';
import MyComponent from './MyComponent.vue';

const meta = {
  title: 'Category/MyComponent',
  component: MyComponent,
  tags: ['autodocs'],
} satisfies Meta<typeof MyComponent>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  render: () => ({
    components: { MyComponent },
    template: '<MyComponent />',
  }),
};
```

### Using Decorators

#### Pinia Decorator

For components that use Pinia stores, use the `withPinia` decorator:

```typescript
import { withPinia } from '../.storybook/decorators/pinia';

export const WithStore: Story = {
  decorators: [withPinia],
  render: () => ({
    components: { MyComponent },
    template: '<MyComponent />',
  }),
};
```

#### Mock Store State

For stories that need specific store state:

```typescript
import { withMockStore } from '../.storybook/decorators/pinia';
import { useMyStore } from '@/stores/my-store';

export const WithCustomState: Story = {
  decorators: [
    withMockStore((pinia) => {
      const myStore = useMyStore(pinia);
      myStore.$patch({
        /* mock state */
      });
    }),
  ],
  render: () => ({
    components: { MyComponent },
    template: '<MyComponent />',
  }),
};
```

### Available Addons

- **`@storybook/addon-a11y`**: Accessibility testing and checks
- **`@storybook/addon-docs`**: Automatic documentation generation

### Global Features

- **Locale Switcher**: Use the toolbar to switch between `en-US` and `fr-CH`
- **Viewport Presets**: Mobile (375px), Tablet (768px), Desktop (1440px)
- **Background Themes**: Light and dark backgrounds
- **Accessibility Checks**: Automatic a11y validation

## Common Troubleshooting Tips

### Storybook Won't Start

**Problem**: Storybook fails to start or shows errors.

**Solutions**:

1. Clear node_modules and reinstall:

   ```bash
   rm -rf node_modules package-lock.json
   npm install
   # Or using Make
   make clean && make install
   ```

2. Clear Storybook cache:

   ```bash
   rm -rf node_modules/.cache
   make storybook
   # Or using npm
   npm run storybook
   ```

3. Check Node.js version (requires Node >= 24):
   ```bash
   node --version
   ```

### Components Not Rendering

**Problem**: Components appear broken or don't render correctly.

**Solutions**:

1. **Missing Quasar setup**: Ensure Quasar plugins are imported in your component or use the global setup in `preview.ts`

2. **Missing router context**: If your component uses `useRouter()` or `$route`, ensure the router is properly initialized (already done in `preview.ts`)

3. **i18n not working**: Check that translation keys exist in `src/i18n/` and that the locale is set correctly

4. **SCSS imports failing**: Verify that SCSS files are in the correct location and that the path aliases in `main.ts` are correct

### Store State Issues

**Problem**: Pinia stores not working or state leaking between stories.

**Solutions**:

1. Use the `withPinia` decorator to ensure a fresh Pinia instance per story:

   ```typescript
   import { withPinia } from '../.storybook/decorators/pinia';

   export const MyStory: Story = {
     decorators: [withPinia],
     // ...
   };
   ```

2. If state persists between stories, ensure you're using `withPinia` or `withMockStore` decorators

### Build Errors

**Problem**: `storybook:build` fails with errors.

**Solutions**:

1. Check for TypeScript errors:

   ```bash
   npm run type-check  # if available
   ```

2. Verify all imports are correct and paths resolve properly

3. Check that all required assets exist in the `public/` directory

4. Ensure all dependencies are installed:
   ```bash
   npm ci
   ```

### Vite Configuration Issues

**Problem**: Vite-specific errors or module resolution failures.

**Solutions**:

1. Check path aliases in `main.ts` - they should match your `tsconfig.json` paths

2. Verify that `publicDir` points to the correct location (`../../public`)

3. Ensure SCSS preprocessor options are correct, especially the `additionalData` import path

### Port Already in Use

**Problem**: Port 6006 is already in use.

**Solutions**:

1. Kill the process using the port:

   ```bash
   lsof -ti:6006 | xargs kill -9
   ```

2. Use a different port:
   ```bash
   # Using npm
   npm run storybook -- -p 6007
   # Note: Makefile doesn't support port override, use npm directly
   ```

### Docker Build Issues

**Problem**: Docker build fails or Storybook doesn't work in container.

**Solutions**:

1. Ensure you're building from the `frontend/` directory:

   ```bash
   cd frontend
   docker build -f Dockerfile.storybook -t storybook .
   ```

2. Check that all source files are copied correctly in the Dockerfile

3. Verify Node.js version in Dockerfile matches your local version

### TypeScript Errors in Stories

**Problem**: TypeScript errors when writing stories.

**Solutions**:

1. Ensure story files use `.ts` extension (not `.js`)

2. Import types correctly:

   ```typescript
   import type { Meta, StoryObj } from '@storybook/vue3';
   ```

3. Use `satisfies` for type checking:
   ```typescript
   const meta = { ... } satisfies Meta<typeof Component>;
   ```

### Missing Styles or Assets

**Problem**: Styles not applied or assets not loading.

**Solutions**:

1. Verify that `app.scss` is imported in `preview.ts`

2. Check that `publicDir` is correctly set in `main.ts` Vite config

3. Ensure asset paths use the correct aliases (`@/assets` or `assets/`)

4. For Quasar styles, verify that `@quasar/extras` CSS files are imported in `preview.ts`

### i18n Not Working

**Problem**: Translations not showing or locale switcher not working.

**Solutions**:

1. Verify translation files exist in `src/i18n/`

2. Check that the locale value matches available locales (`en-US`, `fr-CH`)

3. Ensure `vue-i18n` is properly configured in `preview.ts`

4. Use the locale toolbar control to switch languages in Storybook

## Additional Resources

- [Storybook Documentation](https://storybook.js.org/docs)
- [Vue 3 Storybook Guide](https://storybook.js.org/docs/get-started/vue3)
- [Storybook Testing](https://storybook.js.org/docs/writing-tests)

## Getting Help

If you encounter issues not covered here:

1. Check the Storybook console for detailed error messages
2. Review the browser console for runtime errors
3. Check the terminal output for build/compilation errors
4. Verify your component works in the main application first
