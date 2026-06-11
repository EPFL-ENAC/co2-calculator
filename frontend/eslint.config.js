import pluginVue from 'eslint-plugin-vue';
import globals from 'globals';
import js from '@eslint/js';
import prettier from 'eslint-config-prettier';
import {
  defineConfigWithVueTs,
  vueTsConfigs,
} from '@vue/eslint-config-typescript';

export default defineConfigWithVueTs([
  js.configs.recommended,
  pluginVue.configs['flat/recommended'],
  vueTsConfigs.recommended,
  prettier,

  // 👇 Node environment for Quasar config and CLI scripts
  {
    files: ['quasar.config.js', 'scripts/**/*.{js,mjs,cjs}'],
    languageOptions: {
      globals: {
        ...globals.node, // __dirname, require, process, etc.
      },
    },
  },

  // 👇 Ignore generated and build folders
  {
    ignores: [
      '**/node_modules/',
      '**/dist/',
      '**/.quasar/',
      '**/tests/',
      '**/playwright/',
      '**/test-results/',
      '**/playwright-report/',
      '**/storybook-static/',
      '**/quasar.config.*.temporary.compiled*',
      // public/ is static assets served as-is (no transpile, no module
      // resolution). Linting them as TS/Vue source flags browser globals
      // like `window` as undefined.
      'public/**',
      // Auto-generated from FastAPI OpenAPI schema (see scripts/gen-api-types.mjs).
      // Linting upstream-generated declaration files just creates churn on
      // every regeneration; the generator's own output is the source of truth.
      'src/types/api/openapi.d.ts',
    ],
  },
]);
