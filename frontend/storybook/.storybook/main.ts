import type { StorybookConfig } from '@storybook/vue3-vite';
import path from 'path';
import { fileURLToPath } from 'url';
import { mergeConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

const __dirname = path.dirname(fileURLToPath(import.meta.url));

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
    return mergeConfig(config, {
      plugins: [vue()],
      publicDir: path.resolve(__dirname, '../../public'),
      root: path.resolve(__dirname, '../..'),
      resolve: {
        alias: {
          src: path.resolve(__dirname, '../../src'),
          components: path.resolve(__dirname, '../../src/components'),
          layouts: path.resolve(__dirname, '../../src/layouts'),
          pages: path.resolve(__dirname, '../../src/pages'),
          assets: path.resolve(__dirname, '../../src/assets'),
          boot: path.resolve(__dirname, '../../src/boot'),
          stores: path.resolve(__dirname, '../../src/stores'),
        },
      },
      css: {
        preprocessorOptions: {
          scss: {
            api: 'modern-compiler',
            additionalData: `@use "sass:math"; @import "${path.resolve(__dirname, '../../src/css/02-tokens/quasar-bridge.scss')}";`,
          },
        },
      },
    });
  },
};

export default config;
