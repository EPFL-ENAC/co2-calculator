// This file has been automatically migrated to valid ESM format by Storybook.
import type { StorybookConfig } from '@storybook/vue3-vite';
import path from 'path';
import { fileURLToPath } from 'url';
import { mergeConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { institutionPlugin } from '../../build/institution.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '../..');

// Stories render with the values and assets of institutions/epfl, written by
// the container scripts (#3244). Paths are relative to frontend/.
process.env.INSTITUTION_ENV_FILE ??=
  '../institutions/epfl/frontend.env.example';
process.env.INSTITUTION_ASSETS_DIR ??= '../institutions/epfl/assets';

const config: StorybookConfig = {
  stories: [
    '../../src/components/**/*.stories.@(js|jsx|mjs|ts|tsx)',
    '../stories/**/*.stories.@(js|jsx|mjs|ts|tsx)',
  ],

  addons: ['@storybook/addon-a11y', '@storybook/addon-docs'],

  framework: {
    name: '@storybook/vue3-vite',
    options: {},
  },

  async viteFinal(config) {
    // Remove any existing vue plugins
    const filteredPlugins = (config.plugins || []).filter((plugin) => {
      if (!plugin) return false;
      const pluginName =
        typeof plugin === 'object' && 'name' in plugin ? plugin.name : '';
      return pluginName !== 'vite:vue';
    });

    return mergeConfig(
      { ...config, plugins: filteredPlugins },
      {
        plugins: [vue(), institutionPlugin()],
        resolve: {
          alias: {
            '@': path.resolve(projectRoot, 'src'),
            // See playwright-ct.config.ts for why this is needed: Storybook's
            // own Vite instance doesn't know Quasar's internal '#q-app'
            // alias used by boot/router/store files.
            '#q-app': '@quasar/app-vite',
          },
        },
        css: {
          preprocessorOptions: {
            scss: {
              api: 'modern-compiler',
              silenceDeprecations: ['import'],
            },
          },
        },
        build: {
          assetsInlineLimit: 0,
          rollupOptions: {
            external: [
              // Exclude page components from the build
              /src\/pages\/.*/,
            ],
          },
        },
      },
    );
  },
};

export default config;
