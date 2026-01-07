import type { StorybookConfig } from '@storybook/vue3-vite';
import path from 'path';
import { fileURLToPath } from 'url';
import { mergeConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, '../..');

const config: StorybookConfig = {
  stories: [
    '../../src/components/**/*.stories.@(js|jsx|mjs|ts|tsx)',
    '../stories/**/*.stories.@(js|jsx|mjs|ts|tsx)',
  ],

  staticDirs: ['../../public'],

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
        plugins: [vue()],
        resolve: {
          alias: {
            src: path.resolve(projectRoot, 'src'),
            components: path.resolve(projectRoot, 'src/components'),
            layouts: path.resolve(projectRoot, 'src/layouts'),
            pages: path.resolve(projectRoot, 'src/pages'),
            assets: path.resolve(projectRoot, 'src/assets'),
            boot: path.resolve(projectRoot, 'src/boot'),
            stores: path.resolve(projectRoot, 'src/stores'),
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
            onwarn: (warning, warn) => {
              // Ignore unresolved import warnings for fonts in public folder
              if (
                warning.code === 'UNRESOLVED_IMPORT' &&
                warning.message.includes('/fonts/')
              ) {
                return;
              }
              warn(warning);
            },
          },
        },
      },
    );
  },
};

export default config;
