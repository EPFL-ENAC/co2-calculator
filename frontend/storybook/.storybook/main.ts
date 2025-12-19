import type { StorybookConfig } from '@storybook/vue3-vite';
import path from 'path';
import { fileURLToPath } from 'url';

// ES module equivalent of __dirname
const __dirname = path.dirname(fileURLToPath(import.meta.url));

const config: StorybookConfig = {
  stories: [
    '../../src/components/**/*.stories.@(js|jsx|mjs|ts|tsx)',
    '../stories/**/*.stories.@(js|jsx|mjs|ts|tsx)',
  ],
  addons: [
    '@storybook/addon-a11y',
    // Essentials, interactions, and links are built into Storybook core in 10.x
  ],
  framework: {
    name: '@storybook/vue3-vite',
    options: {},
  },
  viteFinal: async (config) => {
    // Configure path aliases matching Quasar config
    config.resolve = config.resolve || {};
    config.resolve.alias = {
      ...config.resolve.alias,
      src: path.resolve(__dirname, '../../src'),
      'src/*': path.resolve(__dirname, '../../src/*'),
      components: path.resolve(__dirname, '../../src/components'),
      'components/*': path.resolve(__dirname, '../../src/components/*'),
      layouts: path.resolve(__dirname, '../../src/layouts'),
      'layouts/*': path.resolve(__dirname, '../../src/layouts/*'),
      pages: path.resolve(__dirname, '../../src/pages'),
      'pages/*': path.resolve(__dirname, '../../src/pages/*'),
      assets: path.resolve(__dirname, '../../src/assets'),
      'assets/*': path.resolve(__dirname, '../../src/assets/*'),
      stores: path.resolve(__dirname, '../../src/stores'),
      'stores/*': path.resolve(__dirname, '../../src/stores/*'),
    };

    // Configure SCSS preprocessorOptions
    config.css = config.css || {};
    config.css.preprocessorOptions = config.css.preprocessorOptions || {};
    config.css.preprocessorOptions.scss = {
      ...config.css.preprocessorOptions.scss,
      // Import quasar-bridge for variable overrides (matches Quasar config pattern)
      additionalData: `@use "sass:math"; @import "../../src/css/quasar.variables.scss";`,
    };

    return config;
  },
};

export default config;
