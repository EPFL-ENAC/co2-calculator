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
  pluginVue.configs['flat/essential'],
  vueTsConfigs.recommended,
  prettier,

  // 👇 Node environment for Quasar config
  {
    files: ['quasar.config.js'],
    languageOptions: {
      globals: {
        ...globals.node, // __dirname, require, process, etc.
      },
    },
  },

  // 👇 Ignore generated and build folders
  {
    ignores: ['node_modules/', 'dist/', '.quasar/'],
  },
]);
