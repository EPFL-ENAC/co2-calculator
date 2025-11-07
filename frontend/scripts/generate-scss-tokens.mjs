#!/usr/bin/env node
/* eslint-env node */

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

const TOKENS_FILE = path.join(projectRoot, 'src/css/tokens.css');
const OPTIONS_FILE = path.join(projectRoot, 'src/css/02-tokens/_options.scss');
const DECISIONS_FILE = path.join(
  projectRoot,
  'src/css/02-tokens/_decisions.scss',
);
const COMPONENTS_FILE = path.join(
  projectRoot,
  'src/css/02-tokens/_components.scss',
);
const QUASAR_BRIDGE_FILE = path.join(
  projectRoot,
  'src/css/02-tokens/_quasar-bridge.scss',
);

// Options patterns: rem-based primitives with --tokens- prefix
const OPTIONS_PATTERNS = {
  spacing: /^--tokens-spacing-/,
  radius: /^--tokens-border-radius-/,
  fontSize: /^--tokens-typography-font-size-/,
  lineHeight: /^--tokens-typography-line-height-/,
  fontWeight: /^--tokens-typography-font-weight-/,
  fontFamily: /^--tokens-typography-font-family-/,
  colorBrand: /^--tokens-colors-(red|blue|grey-scale|base|status)-/,
  layout: /^--tokens-layout-/,
};

// Decisions patterns: semantic layer (NO --tokens- prefix)
const DECISIONS_PATTERNS = {
  layout: /^--layout-/,
  color: /^--color-/,
  spacing: /^--spacing-/,
  radius: /^--radius-/,
  text: /^--text-/,
};

// Component patterns
const COMPONENT_PATTERNS = {
  button: /^--button-/,
  field: /^--field-/,
  form: /^--form-/,
  card: /^--card-/,
  timeline: /^--timeline-/,
  icon: /^--icon-/,
  radio: /^--radio-/,
  checkbox: /^--checkbox-/,
  statusIndicator: /^--status-indicator-/,
  popUp: /^--pop-up-/,
  table: /^--table-/,
  template: /^--template-/,
  container: /^--container-/,
  tabs: /^--tabs-/,
};

function toScssVariable(cssName) {
  let name = cssName.replace(/^--+/, '');
  name = name.replace(/^_+/, '');
  name = name.replace(/_/g, '-');
  name = name.replace(/-{2,}/g, '-');
  return `$${name}`;
}

function classifyToken(cssName) {
  // Check options first (tokens-* patterns)
  for (const [category, pattern] of Object.entries(OPTIONS_PATTERNS)) {
    if (pattern.test(cssName)) {
      return { layer: 'options', category };
    }
  }

  // Check decisions second (NO tokens- prefix)
  for (const [category, pattern] of Object.entries(DECISIONS_PATTERNS)) {
    if (pattern.test(cssName)) {
      return { layer: 'decisions', category };
    }
  }

  // Check components
  for (const [category, pattern] of Object.entries(COMPONENT_PATTERNS)) {
    if (pattern.test(cssName)) {
      return { layer: 'components', category };
    }
  }

  // Default to components for anything else
  return { layer: 'components', category: 'misc' };
}

function replaceVars(rawValue, recordMap, currentLayer) {
  return rawValue.replace(/var\(\s*(--[\w-]+)\s*\)/g, (_, matchName) => {
    const reference = recordMap.get(matchName);
    if (!reference) {
      globalThis.console.warn(
        `⚠️  Unknown reference ${matchName} in value ${rawValue}`,
      );
      return `var(${matchName})`;
    }

    if (currentLayer === 'options') {
      return reference.scssName;
    }

    if (reference.layer === 'options') {
      return `opt.${reference.scssName}`;
    }

    if (currentLayer === 'components' && reference.layer === 'decisions') {
      return `dec.${reference.scssName}`;
    }

    return reference.scssName;
  });
}

function groupByCategory(records) {
  const grouped = {};
  for (const record of records) {
    if (!grouped[record.category]) {
      grouped[record.category] = [];
    }
    grouped[record.category].push(record);
  }
  return grouped;
}

function getCategoryComment(category) {
  const comments = {
    // Options
    spacing: 'Spacing',
    radius: 'Border Radius',
    fontFamily: 'Font Family',
    fontSize: 'Font Size',
    lineHeight: 'Line Height',
    fontWeight: 'Font Weight',
    colorBrand: 'Colors',
    layout: 'Layout',

    // Decisions
    color: 'Brand Palette',
    text: 'Typography',
    radii: 'Radii',

    // Components
    button: 'Buttons',
    field: 'Form Fields',
    form: 'Forms',
    card: 'Cards',
    timeline: 'Timeline',
    icon: 'Icons',
    radio: 'Radio Buttons',
    checkbox: 'Checkboxes',
    statusIndicator: 'Status Indicators',
    popUp: 'Pop-ups',
    table: 'Tables',
    template: 'Templates',
    container: 'Containers',
    tabs: 'Tabs',
    misc: 'Miscellaneous',
  };
  return comments[category] || category;
}

function generateScssContent(records, recordMap, layer, useStatements = '') {
  const grouped = groupByCategory(records);
  const lines = [];

  const categoryOrder = {
    options: [
      'spacing',
      'radius',
      'fontFamily',
      'fontSize',
      'lineHeight',
      'fontWeight',
      'colorBrand',
      'layout',
    ],
    decisions: ['color', 'spacing', 'radius', 'text', 'layout'],
    components: [
      'button',
      'form',
      'field',
      'card',
      'timeline',
      'icon',
      'radio',
      'checkbox',
      'statusIndicator',
      'popUp',
      'table',
      'template',
      'container',
      'tabs',
      'misc',
    ],
  };

  const orderedCategories = categoryOrder[layer] || Object.keys(grouped).sort();

  for (const category of orderedCategories) {
    if (!grouped[category]) continue;

    lines.push('');
    lines.push(`// ${getCategoryComment(category)}`);
    for (const record of grouped[category]) {
      const value = replaceVars(record.rawValue, recordMap, layer);
      lines.push(`${record.scssName}: ${value} !default;`);
    }
  }

  const header = `// -----------------------------------------------------------------------------
// ⚠️  Auto-generated file
// -----------------------------------------------------------------------------
// Generated from src/css/tokens.css via scripts/generate-scss-tokens.mjs
// Do not edit manually.

${useStatements}`;

  return header + lines.join('\n') + '\n';
}

function generateDecisionsManualContent() {
  // Manual semantic tokens that bridge options to meaningful names
  return `@use 'options' as opt;

// Brand Palette
$color-primary: opt.$tokens-colors-red-red-100 !default;
$color-primary-hover: opt.$tokens-colors-red-red-200 !default;
$color-secondary: opt.$tokens-colors-grey-scale-grey-200 !default;
$color-surface: opt.$tokens-colors-base-white !default;
$color-surface-muted: opt.$tokens-colors-grey-scale-grey-100 !default;
$color-border: opt.$tokens-colors-grey-scale-grey-300 !default;
$color-text: opt.$tokens-colors-base-black !default;
$color-text-muted: opt.$tokens-colors-grey-scale-grey-500 !default;
$color-text-on-primary: opt.$tokens-colors-base-white !default;

// Status Colors
$color-status-success: opt.$tokens-colors-status-green !default;
$color-status-warning: opt.$tokens-colors-status-yellow !default;
$color-status-error: opt.$tokens-colors-status-red !default;

// Spacing scale (semantic naming)
$spacing-xxs: opt.$tokens-spacing-1 !default;
$spacing-xs: opt.$tokens-spacing-4 !default;
$spacing-sm: opt.$tokens-spacing-8 !default;
$spacing-md: opt.$tokens-spacing-12 !default;
$spacing-lg: opt.$tokens-spacing-16 !default;
$spacing-xl: opt.$tokens-spacing-24 !default;
$spacing-xxl: opt.$tokens-spacing-32 !default;
$spacing-page: opt.$tokens-spacing-48 !default;

// Radii
$radius-default: opt.$tokens-border-radius-generic-border-radius !default;
$radius-default-px: opt.$tokens-border-radius-generic-border-radius-px !default;
$radius-pill: opt.$tokens-border-radius-full-border-radius !default;

// Typography
$text-font-family: opt.$tokens-typography-font-family-base !default;
$text-size-xs: opt.$tokens-typography-font-size-xs !default;
$text-size-sm: opt.$tokens-typography-font-size-sm !default;
$text-size-base: opt.$tokens-typography-font-size-md !default;
$text-size-lg: opt.$tokens-typography-font-size-lg !default;
$text-line-height-tight: opt.$tokens-typography-line-height-xs !default;
$text-line-height-base: opt.$tokens-typography-line-height-md !default;
$text-line-height-loose: opt.$tokens-typography-line-height-lg !default;
$text-weight-regular: opt.$tokens-typography-font-weight-regular !default;
$text-weight-medium: opt.$tokens-typography-font-weight-medium !default;
$text-weight-bold: opt.$tokens-typography-font-weight-bold !default;

// Layout
$layout-page-width: opt.$tokens-layout-page-width !default;
$layout-pop-up-min-width: 21.875rem !default;
`;
}

// /* Quasar bridge generation
// ** CF: https://quasar.dev/style/variables-and-styling#introduction-to-quasar-sass-variables
// ** https://quasar.dev/style/sass-scss-variables#variables-list
// */
function generateQuasarBridge() {
  return `// -----------------------------------------------------------------------------
// ⚠️  Auto-generated file
// -----------------------------------------------------------------------------
// Quasar Bridge
// Maps the token system onto Quasar's variable names. Import this file before
// loading Quasar's source styles.
// Generated from src/css/tokens.css via scripts/generate-scss-tokens.mjs
// Do not edit manually.
// Reference: https://quasar.dev/style/sass-scss-variables#variables-list
// -----------------------------------------------------------------------------

@use 'components' as comp;
@use 'decisions' as dec;
@use 'options' as opt;

// Brand colors
$primary: dec.$color-primary;
$secondary: dec.$color-secondary;
$accent: dec.$color-primary-hover !default;
$dark: #1d1d1d !default;
$dark-page: #121212 !default;
$positive: dec.$color-status-success !default;
$negative: dec.$color-status-error !default;
$info: dec.$color-status-warning !default;
$warning: dec.$color-status-warning !default;

// Spacing
$space-base: dec.$spacing-md !default;
$space-x-base: $space-base !default;
$space-y-base: $space-base !default;
$space-none: (
  x: 0,
  y: 0,
) !default;
$space-xs: (
  x: dec.$spacing-xs,
  y: dec.$spacing-xs,
) !default;
$space-sm: (
  x: dec.$spacing-sm,
  y: dec.$spacing-sm,
) !default;
$space-md: (
  x: dec.$spacing-md,
  y: dec.$spacing-md,
) !default;
$space-lg: (
  x: dec.$spacing-lg,
  y: dec.$spacing-lg,
) !default;
$space-xl: (
  x: dec.$spacing-xl,
  y: dec.$spacing-xl,
) !default;

// Typography
$body-font-size: dec.$text-size-sm !default;
$body-line-height: dec.$text-line-height-base !default;
$typography-font-family: dec.$text-font-family !default;

// Button
$button-border-radius: comp.$button-radius !default;
$button-rounded-border-radius: comp.$button-radius-rounded !default;
$button-push-border-radius: comp.$button-radius !default;
$button-padding: comp.$button-size-md-padding-y comp.$button-size-md-padding-x !default;
$button-dense-padding: comp.$button-size-sm-padding-y comp.$button-size-sm-padding-x !default;
$button-font-size: comp.$button-size-md-font-size !default;
$button-line-height: comp.$button-size-md-line-height !default;
$button-font-weight: dec.$text-weight-medium !default;
$button-shadow: none !default;
$button-shadow-active: none !default;
$button-transition: 0.3s ease !default;

// Separators & borders
$separator-color: dec.$color-border !default;
$separator-dark-color: rgb(255 255 255 / 28%) !default;
$generic-border-radius: dec.$radius-default-px !default;

// Input/Form fields
$input-font-size: comp.$field-sm-font-size !default;
$input-text-color: dec.$color-text !default;
$input-label-color: dec.$color-text-muted !default;

// Cards
$generic-hover-transition: 0.3s cubic-bezier(0.25, 0.8, 0.5, 1) !default;

// Dimmed backgrounds
$dimmed-background: rgb(0 0 0 / 40%) !default;
$light-dimmed-background: rgb(255 255 255 / 60%) !default;

// Menu
$menu-background: dec.$color-surface !default;
$menu-max-width: 95vw !default;
$menu-max-height: 65vh !default;

// Tooltip
$tooltip-color: #fafafa !default;
$tooltip-background: opt.$tokens-colors-grey-scale-grey-600 !default;
$tooltip-padding: dec.$spacing-xs dec.$spacing-sm !default;
$tooltip-border-radius: dec.$radius-default !default;
$tooltip-fontsize: dec.$text-size-xs !default;
$tooltip-mobile-padding: dec.$spacing-sm dec.$spacing-md !default;
$tooltip-mobile-fontsize: dec.$text-size-sm !default;
$tooltip-max-width: 95vw !default;
$tooltip-max-height: 65vh !default;

// Table
$table-border-color: dec.$color-border !default;
$table-hover-background: rgb(0 0 0 / 3%) !default;
$table-selected-background: rgb(0 0 0 / 6%) !default;
$table-dark-border-color: $separator-dark-color !default;
$table-dark-hover-background: rgb(255 255 255 / 7%) !default;
$table-dark-selected-background: rgb(255 255 255 / 10%) !default;
$table-border-radius: dec.$radius-default !default;
$table-transition: $generic-hover-transition !default;

// Layout
$layout-border: 1px solid $separator-color !default;

// Badge
$badge-font-size: dec.$text-size-xs !default;
$badge-line-height: 1 !default;

// Item (lists)
$item-base-color: opt.$tokens-colors-grey-scale-grey-500 !default;

// Editor
$editor-border-color: $separator-color !default;
$editor-border-dark-color: $separator-dark-color !default;
$editor-content-padding: dec.$spacing-sm !default;
$editor-content-min-height: 10em !default;
$editor-toolbar-padding: dec.$spacing-xs !default;
$editor-hr-color: $editor-border-color !default;
$editor-hr-dark-color: $editor-border-dark-color !default;
$editor-button-gutter: dec.$spacing-xs !default;

// Chat
$chat-message-received-color: #000 !default;
$chat-message-received-bg: opt.$tokens-colors-status-green !default;
$chat-message-sent-color: #000 !default;
$chat-message-sent-bg: opt.$tokens-colors-grey-scale-grey-400 !default;
$chat-message-border-radius: dec.$radius-default !default;
$chat-message-distance: dec.$spacing-sm !default;
$chat-message-text-padding: dec.$spacing-sm !default;

// Dialog
$dialog-title-font-size: dec.$text-size-lg !default;
$dialog-title-line-height: 1.6 !default;

// Toolbar
$toolbar-min-height: 50px !default;
$toolbar-padding: 0 dec.$spacing-md !default;
$toolbar-title-font-size: dec.$text-size-lg !default;
$toolbar-title-font-weight: dec.$text-weight-regular !default;
$toolbar-title-padding: 0 dec.$spacing-md !default;

// Rating
$rating-grade-color: opt.$tokens-colors-status-yellow !default;


// CRITICAL MANUAL FIXES FOR Z-INDEX AND FLEXBOX VARIABLES
// Quasar does not provide default values for these, so we need to set them here.
$breakpoint-xs: 599px !default;
$breakpoint-sm: 1023px !default;
$breakpoint-md: 1439px !default;
$breakpoint-lg: 1919px !default;

$z-fab: 990 !default;
$z-side: 1000 !default;
$z-marginals: 2000 !default;
$z-fixed-drawer: 3000 !default;
$z-fullscreen: 6000 !default;
$z-menu: 6000 !default;
$z-top: 7000 !default;
$z-tooltip: 9000 !default;
$z-notify: 9500 !default;
$z-max: 9998 !default;

$flex-cols: 12 !default;
$flex-gutter-xs: dec.$spacing-xs !default;
$flex-gutter-sm: dec.$spacing-sm !default;
$flex-gutter-md: dec.$spacing-md !default;
$flex-gutter-lg: dec.$spacing-lg !default;
$flex-gutter-xl: dec.$spacing-xl !default;
`;
}

async function run() {
  const cssContent = await fs.readFile(TOKENS_FILE, 'utf8');
  const varRegex = /(--[\w-]+)\s*:\s*([^;]+);/g;

  const allRecords = [];
  const recordMap = new Map();

  let match;
  while ((match = varRegex.exec(cssContent)) !== null) {
    const cssName = match[1];
    const rawValue = match[2].trim();
    const { layer, category } = classifyToken(cssName);
    const scssName = toScssVariable(cssName);

    const record = {
      cssName,
      scssName,
      layer,
      category,
      rawValue,
    };

    allRecords.push(record);
    recordMap.set(cssName, record);
  }

  // Separate records by layer
  const optionsRecords = allRecords.filter((r) => r.layer === 'options');
  const decisionsRecords = allRecords.filter((r) => r.layer === 'decisions');
  const componentsRecords = allRecords.filter((r) => r.layer === 'components');

  // Generate options file
  const optionsContent = generateScssContent(
    optionsRecords,
    recordMap,
    'options',
  );
  await fs.writeFile(OPTIONS_FILE, optionsContent);
  globalThis.console.log(`✓ Generated ${OPTIONS_FILE}`);

  // Generate decisions file - keep manual for now
  const decisionsHeader = `// -----------------------------------------------------------------------------
// ⚠️  Auto-generated file
// -----------------------------------------------------------------------------
// Generated from src/css/tokens.css via scripts/generate-scss-tokens.mjs
// Do not edit manually.

`;
  const decisionsContent = decisionsHeader + generateDecisionsManualContent();
  await fs.writeFile(DECISIONS_FILE, decisionsContent);
  globalThis.console.log(`✓ Generated ${DECISIONS_FILE}`);

  // Generate components file - FULLY AUTO-GENERATED
  const componentsContent = generateScssContent(
    componentsRecords,
    recordMap,
    'components',
    "@use 'decisions' as dec;\n@use 'options' as opt;",
  );
  await fs.writeFile(COMPONENTS_FILE, componentsContent);
  globalThis.console.log(`✓ Generated ${COMPONENTS_FILE}`);

  // Generate Quasar bridge file
  const quasarBridgeContent = generateQuasarBridge();
  await fs.writeFile(QUASAR_BRIDGE_FILE, quasarBridgeContent);
  globalThis.console.log(`✓ Generated ${QUASAR_BRIDGE_FILE}`);

  // Summary
  globalThis.console.log('');
  globalThis.console.log('Summary:');
  globalThis.console.log(`  Options:    ${optionsRecords.length} primitives`);
  globalThis.console.log(
    `  Decisions:  ${decisionsRecords.length} tokens found (using manual template)`,
  );
  globalThis.console.log(
    `  Components: ${componentsRecords.length} component tokens`,
  );
  globalThis.console.log(`  Total CSS:  ${allRecords.length} tokens parsed`);
}

run().catch((error) => {
  globalThis.console.error('Failed to generate Sass tokens:', error);
  globalThis.process.exit(1);
});
