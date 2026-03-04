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
    // `no-invalid-position-at-import-rule` is disabled for `@layer` blocks because
    // our CSS architecture intentionally uses `@import` inside `@layer` declarations
    // to control cascade order (ITCSS-inspired layering via native CSS `@layer`).
    //
    // This is valid modern CSS — stylelint just doesn't recognize `@import` inside
    // `@layer` as a legitimate position.
    //
    // ⚠️  Do NOT migrate to `@use` as a quick fix — it changes SCSS namespacing
    // and requires a deliberate refactor. See src/css/app.scss for the full layer
    // architecture and docs/src/frontend/02-design-tokens for the decision rationale.
    'no-invalid-position-at-import-rule': [true, { ignoreAtRules: ['layer'] }],
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
