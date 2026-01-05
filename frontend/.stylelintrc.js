/** @type {import('stylelint').Config} */
export default {
  extends: [
    'stylelint-config-standard-scss',
    'stylelint-config-recommended-vue/scss',
  ],
  rules: {
    // Allow both kebab-case and your custom naming patterns
    // This allows: --my-var, ---my-var, --_my-var, etc.
    'custom-property-pattern': '^_?-*[a-z][a-z0-9]*(-[a-z0-9]+)*$',

    // Allow both short and long hex colors
    'color-hex-length': null,

    // Selector class pattern - allow BEM and other conventions
    'selector-class-pattern': null,

    // Add custom rules here as needed
  },
  ignoreFiles: [
    '**/*.min.css',
    '**/dist/**',
    '**/.quasar/**',
    '**/build/**',
    '**/node_modules/**',
    '**/storybook-static/**',
    '**/test-results/**',
    '**/playwright-report/**',
    // Ignore auto-generated token files if needed
  ],
};
