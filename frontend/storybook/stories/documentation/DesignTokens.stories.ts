import type { Meta, StoryObj } from '@storybook/vue3';
import { defineComponent, h, type VNode } from 'vue';

/**
 * Design Tokens Documentation
 *
 * This page documents all design tokens used in the application, organized in a three-layer hierarchy:
 * 1. **Options** (_options.scss): Raw primitive values
 * 2. **Decisions** (_decisions.scss): Semantic naming for design decisions
 * 3. **Components** (_components.scss): Component-specific token mappings
 */

// ============================================================================
// TOKEN DATA - Extracted from actual SCSS files
// ============================================================================

const optionsTokens = {
  spacing: {
    1: '0.0625rem (1px)',
    2: '0.125rem (2px)',
    4: '0.25rem (4px)',
    8: '0.5rem (8px)',
    12: '0.75rem (12px)',
    16: '1rem (16px)',
    24: '1.5rem (24px)',
    32: '2rem (32px)',
    48: '3rem (48px)',
    64: '4rem (64px)',
  },
  borderRadius: {
    'generic-border-radius': '0.1875rem (3px)',
    'generic-border-radius-px': '3px',
    'full-border-radius': '62.4375rem',
    'lg-border-radius': '0.75rem (12px)',
  },
  typography: {
    fontFamily: "'SuisseIntl', '-apple-system', sans-serif",
    fontSizes: {
      '3xl': '1.75rem (28px)',
      '2xl': '1.5rem (24px)',
      xl: '1.25rem (20px)',
      lg: '1.125rem (18px)',
      md: '1rem (16px)',
      sm: '0.875rem (14px)',
      xs: '0.75rem (12px)',
      '2xs': '0.625rem (10px)',
    },
    lineHeights: {
      '4xl': '2.25rem (36px)',
      '3xl': '2rem (32px)',
      '2xl': '1.75rem (28px)',
      xl: '1.625rem (26px)',
      lg: '1.5rem (24px)',
      md: '1.25rem (20px)',
      sm: '1.125rem (18px)',
      xs: '1rem (16px)',
      '2xs': '0.875rem (14px)',
    },
    fontWeights: {
      regular: '400',
      medium: '500',
      bold: '700',
    },
  },
  iconSizes: {
    sm: '18px',
    md: '32px',
    lg: '48px',
  },
  colors: {
    status: {
      green: '#28a745',
      red: '#dc3545',
      yellow: '#ffc107',
    },
    greyScale: {
      100: '#f5f5f5',
      200: '#e6e6e6',
      300: '#d5d5d5',
      400: '#c1c1c1',
      500: '#8e8e8e',
      600: '#707070',
    },
    accent: {
      leman: '#00a79f',
      canard: '#007480',
    },
    red: {
      100: '#ff0000',
      200: '#b51f1f',
      highlight: '#fbeceb',
      'highlight-200': '#f4c6c2',
    },
    base: {
      black: '#212121',
      white: '#ffffff',
    },
  },
  layout: {
    'page-width': '1320px',
    'lg-modal-width': '75rem',
    'md-modal-width': '30rem',
    'sm-modal-width': '20rem',
    'full-width': '100%',
    'full-height': '100%',
  },
  transitions: {
    default: '0.2s ease',
  },
  boxShadow: 'rgb(99 99 99 / 40%) 0px 2px 8px 0px',
  zIndex: {
    'background-base': '-2',
    'background-overlay': '-1',
    top: '99',
  },
};

const decisionsTokens = {
  colors: {
    brand: {
      primary: '#ff0000',
      'primary-hover': '#b51f1f',
      secondary: '#e6e6e6',
    },
    semantic: {
      surface: '#ffffff',
      'surface-muted': '#f5f5f5',
      text: '#212121',
      'text-muted': '#8e8e8e',
      'text-on-primary': '#ffffff',
      border: '#d5d5d5',
    },
    status: {
      validated: '#007480',
      success: '#28a745',
      warning: '#ffc107',
      error: '#dc3545',
    },
  },
  spacing: {
    xxs: '0.0625rem (1px)',
    xs: '0.25rem (4px)',
    sm: '0.5rem (8px)',
    md: '0.75rem (12px)',
    lg: '1rem (16px)',
    xl: '1.5rem (24px)',
    xxl: '2rem (32px)',
    page: '3rem (48px)',
  },
  borderRadius: {
    default: '0.1875rem (3px)',
    'default-px': '3px',
    pill: '62.4375rem',
  },
  typography: {
    fontFamily: "'SuisseIntl', '-apple-system', sans-serif",
    fontSizes: {
      '2xs': '0.625rem (10px)',
      xs: '0.75rem (12px)',
      sm: '0.875rem (14px)',
      base: '1rem (16px)',
      lg: '1.125rem (18px)',
      xl: '1.25rem (20px)',
      '2xl': '1.5rem (24px)',
      '3xl': '1.75rem (28px)',
    },
    lineHeights: {
      '2xs': '0.875rem (14px)',
      xs: '1rem (16px)',
      sm: '1.125rem (18px)',
      base: '1.25rem (20px)',
      lg: '1.5rem (24px)',
      xl: '1.625rem (26px)',
      '2xl': '1.75rem (28px)',
      '3xl': '2rem (32px)',
      '4xl': '2.25rem (36px)',
    },
    fontWeights: {
      regular: '400',
      medium: '500',
      bold: '700',
    },
  },
  layout: {
    'page-width': '1320px',
    'pop-up-lg-min-width': '30rem',
    'pop-up-min-width': '20rem',
    'page-padding-x': '1rem (16px)',
    'page-padding-y': '3rem (48px)',
    'gap-y': '1.5rem (24px)',
  },
  modal: {
    'width-lg': '75rem',
    'width-md': '30rem',
    'width-sm': '20rem',
  },
  icons: {
    'size-sm': '18px',
    'size-md': '32px',
    'size-lg': '48px',
  },
  tooltip: {
    color: '#212121',
    background: '#ffffff',
    fontsize: '0.875rem (14px)',
    'line-height': '1.75rem (28px)',
    'padding-x': '2rem (32px)',
    'padding-y': '3rem (48px)',
    'max-width': '30rem',
    'border-radius': '0.1875rem (3px)',
    'box-shadow': 'rgb(99 99 99 / 40%) 0px 2px 8px 0px',
  },
};

const componentTokens = {
  header: {
    bg: '#ffffff',
    'border-bottom': '#c1c1c1',
    'border-bottom-weight': '0.0625rem (1px)',
    'z-index': '99',
    'padding-x': '2rem (32px)',
    'padding-y': '0.5rem (8px)',
    'min-height': '2rem (32px)',
    'gap-sm-x': '1rem (16px)',
    'gap-lg-x': '3rem (48px)',
    'gap-y': '1rem (16px)',
    'logo-height': '1.5rem (24px)',
    'title-font-size': '1rem (16px)',
    'title-font-weight': '500',
    'title-color': '#212121',
  },
  button: {
    radius: '0.1875rem (3px)',
    'primary-bg-default': '#ff0000',
    'primary-bg-hover': '#b51f1f',
    'primary-color': '#ffffff',
    'secondary-bg-default': '#ffffff',
    'secondary-bg-hover': '#f5f5f5',
    'secondary-color': '#212121',
    'secondary-border-color': '#c1c1c1',
    'disabled-bg': '#e6e6e6',
    'disabled-color': '#c1c1c1',
    'disabled-border-color': '#c1c1c1',
    'size-md-padding-x': '1rem (16px)',
    'size-md-padding-y': '0.75rem (12px)',
    'size-sm-padding-x': '0.5rem (8px)',
    'size-sm-padding-y': '0.25rem (4px)',
    'size-xs-padding-x': '0.75rem (12px)',
    'size-xs-padding-y': '0.5rem (8px)',
    'size-md-font-size': '1rem (16px)',
    'size-md-line-height': '1.25rem (20px)',
    'size-sm-font-size': '0.75rem (12px)',
    'size-sm-line-height': '1.125rem (18px)',
    'size-xs-font-size': '0.75rem (12px)',
    'size-xs-line-height': '1rem (16px)',
    'transition-duration': '0.2s ease',
  },
  field: {
    'min-width': '4rem (64px)',
    'md-padding-x': '0.75rem (12px)',
    'md-padding-y': '0.5rem (8px)',
    'md-font-size': '1rem (16px)',
    'md-line-height': '1.25rem (20px)',
    'md-gap': '0.25rem (4px)',
    'md-font-weight': '500',
    'lg-padding-x': '1rem (16px)',
    'lg-padding-y': '0.75rem (12px)',
    'lg-font-size': '1.125rem (18px)',
    'lg-line-height': '1.5rem (24px)',
    'lg-gap': '0.5rem (8px)',
    'lg-font-weight': '700',
    'border-radius': '0.1875rem (3px)',
    'bg-default': '#ffffff',
    'bg-disabled': '#e6e6e6',
    'color-default': '#212121',
    'color-disabled': '#c1c1c1',
    'border-disabled': '#c1c1c1',
    'color-placeholder': '#707070',
    'border-weight': '0.0625rem (1px)',
    'border-default': '#c1c1c1',
    'border-focus': '#8e8e8e',
    'transition-duration': '0.2s ease',
  },
  timeline: {
    'item-size': '1.5rem (24px)',
    'item-selected-size': '1rem (16px)',
    'item-selected-bg': '#707070',
    'item-border-weight': '0.0625rem (1px)',
    'border-color': '#d5d5d5',
    'item-default-icon': '#707070',
    'item-default-bg': '#707070',
    'item-default-border-color': '#707070',
    'item-default-text': '#707070',
    'item-default-selected-bg': '#8e8e8e',
    'item-in-progress-icon': '#c1c1c1',
    'item-in-progress-bg': '#8e8e8e',
    'item-in-progress-border-color': '#ffffff',
    'item-in-progress-text': '#c1c1c1',
    'item-in-progress-selected-bg': '#8e8e8e',
    'item-validated-icon': '#ff0000',
    'item-validated-bg': '#ff0000',
    'item-validated-border-color': '#ffffff',
    'item-validated-text': '#ff0000',
    'item-validated-selected-bg': '#ff0000',
  },
  icon: {
    'icon-size-xl': '2rem (32px)',
    'icon-size-lg': '1.5rem (24px)',
    'icon-size-md': '1rem (16px)',
    'icon-size-sm': '1rem (16px)',
    'color-grey': '#707070',
    'color-red': '#ff0000',
    'color-black': '#212121',
    'color-white': '#ffffff',
  },
  radio: {
    'selected-radio-color': '#ff0000',
    'selected-text-color': '#212121',
    'button-size': '1rem (16px)',
    'unselected-radio-color': '#707070',
    'unselected-text-color': '#212121',
    'disabled-radio-color': '#c1c1c1',
    'disabled-text-color': '#c1c1c1',
    gap: '0.25rem (4px)',
  },
  checkbox: {
    'selected-radio-color': '#ff0000',
    'button-size': '1rem (16px)',
    'selected-text-color': '#212121',
    'unselected-radio-color': '#707070',
    'unselected-text-color': '#212121',
    gap: '0.25rem (4px)',
    'disabled-radio-color': '#c1c1c1',
    'disabled-text-color': '#c1c1c1',
    checkmark: '#ffffff',
  },
  progressBar: {
    height: '0.25rem (4px)',
    bg: '#e6e6e6',
    'selected-bg': '#f4c6c2',
    'fill-bg': '#ff0000',
  },
  statusIndicator: {
    'high-bg': '#ff0000',
    'high-color': '#ffffff',
    'low-bg': '#e6e6e6',
    'low-color': '#707070',
    'border-radius': '62.4375rem',
    'font-size': '0.625rem (10px)',
    'line-height': '0.875rem (14px)',
    'complete-bg': '#28a745',
    'complete-color': '#ffffff',
    'disabled-bg': '#e6e6e6',
    'disabled-color': '#c1c1c1',
    'disabled-border': '#c1c1c1',
    'padding-x': '0.75rem (12px)',
    'padding-y': '0.5rem (8px)',
  },
  popUp: {
    'min-width': '20rem',
    'padding-y': '1rem (16px)',
    gap: '0.75rem (12px)',
    bg: '#ffffff',
    'divider-color': '#e6e6e6',
    'divider-weight': '0.0625rem (1px)',
    color: '#212121',
  },
  table: {
    'padding-x': '0.75rem (12px)',
    'padding-y': '0.5rem (8px)',
    gap: '2rem (32px)',
    'bg-even': '#f5f5f5',
    'bg-odd': '#ffffff',
    'color-primary': '#212121',
    'color-selected': '#fbeceb',
    'color-disabled': '#c1c1c1',
    'border-weight': '0.0625rem (1px)',
    'border-color': '#c1c1c1',
    'color-secondary': '#707070',
    'border-radius': '0.1875rem (3px)',
    'color-warning': '#dc3545',
    'color-success': '#28a745',
  },
  template: {
    width: '1320px',
    'padding-y': '3rem (48px)',
    gap: '2rem (32px)',
    bg: '#ffffff',
  },
  container: {
    'padding-x': '1.5rem (24px)',
    'padding-y': '1.5rem (24px)',
    'padding-sm-x': '1rem (16px)',
    'padding-sm-y': '1rem (16px)',
    'gap-y': '1.5rem (24px)',
    'default-bg': '#ffffff',
    'divider-weight': '0.0625rem (1px)',
    'divider-default': '#e6e6e6',
    'disabled-bg': '#c1c1c1',
    'default-border': '#d5d5d5',
    'border-radius': '0.1875rem (3px)',
    primary: '#212121',
    secondary: '#707070',
    'disabled-color': '#c1c1c1',
    'divider-disabled': '#e6e6e6',
    'border-weight': '0.0625rem (1px)',
    'selected-hover-bg': '#fbeceb',
    'selected-hover-border': '#ff0000',
    'gap-x': '0.25rem (4px)',
    'hover-bg': '#ffffff',
    'hover-border': '#ff0000',
    'disabled-bg-fill': '#f5f5f5',
  },
  tabs: {
    'selected-bg': '#ff0000',
    'selected-border': '#ff0000',
    'default-bg': '#ffffff',
    'default-border': '#e6e6e6',
    'selected-color': '#ffffff',
    'default-color': '#212121',
    gap: '0.5rem (8px)',
    'padding-y': '0.75rem (12px)',
    'corner-border-radius': '0.75rem (12px)',
    'padding-x': '1.5rem (24px)',
  },
  loginCard: {
    'border-radius': '0.1875rem (3px)',
    'box-shadow': 'rgb(99 99 99 / 40%) 0px 2px 8px 0px',
    padding: '1rem (16px)',
    gap: '0.75rem (12px)',
    bg: '#ffffff',
    color: '#212121',
    'font-size': '1rem (16px)',
    'font-weight': '500',
    'line-height': '1.25rem (20px)',
  },
  loginPage: {
    width: '100%',
    height: '100%',
    'bg-image': '#ffffff',
    'bg-blur': '0px',
    'bg-opacity': '0.75',
    'bg-color': '#ffffff',
    'bg-z-index': '-2',
    'bg-blur-z-index': '-1',
  },
  sidebar: {
    width: '4rem (64px)',
    'padding-left': '2rem (32px)',
    'padding-right': '3rem (48px)',
    'padding-y': '0.5rem (8px)',
    bg: '#e6e6e6',
    'bg-selected': '#c1c1c1',
    'border-width': '0.0625rem (1px)',
    'border-color': '#c1c1c1',
    color: '#212121',
    'item-gap': '0.5rem (8px)',
  },
  graphCard: {
    padding: '1rem (16px)',
    'color-primary': '#00a79f',
    'font-weight': '500',
    'font-size': '0.875rem (14px)',
    'line-height': '1.125rem (18px)',
  },
  moduleResult: {
    bg: '#e6e6e6',
    'border-color': '#d5d5d5',
    'border-weight': '0.0625rem (1px)',
    'border-radius': '0.1875rem (3px)',
    'padding-x': '1rem (16px)',
    'padding-y': '0.5rem (8px)',
  },
};

// ============================================================================
// DOCUMENTATION COMPONENT
// ============================================================================

// eslint-disable-next-line vue/one-component-per-file
const DesignTokensDocumentation = defineComponent({
  name: 'DesignTokensDocumentation',
  setup() {
    const Section = (title: string, children: VNode | VNode[]) => {
      return h('div', { style: { marginBottom: '3rem' } }, [
        h(
          'h2',
          {
            style: {
              fontSize: '1.5rem',
              fontWeight: '600',
              marginBottom: '1rem',
              color: '#212121',
            },
          },
          title,
        ),
        children,
      ]);
    };

    const SubSection = (title: string, children: VNode | VNode[]) => {
      return h('div', { style: { marginBottom: '2rem' } }, [
        h(
          'h3',
          {
            style: {
              fontSize: '1.25rem',
              fontWeight: '500',
              marginBottom: '0.75rem',
              color: '#212121',
            },
          },
          title,
        ),
        children,
      ]);
    };

    const CodeBlock = (code: string) => {
      return h(
        'pre',
        {
          style: {
            margin: '1rem 0',
            padding: '1rem',
            fontSize: '0.875rem',
            lineHeight: '1.6',
            fontFamily:
              "'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace",
            backgroundColor: '#f5f5f5',
            border: '1px solid #e6e6e6',
            borderRadius: '3px',
            overflow: 'auto',
          },
        },
        h('code', { style: { display: 'block', whiteSpace: 'pre' } }, code),
      );
    };

    return () =>
      h(
        'div',
        {
          style: {
            padding: '2rem',
            maxWidth: '1200px',
            margin: '0 auto',
            fontFamily: "'SuisseIntl', '-apple-system', sans-serif",
            lineHeight: '1.6',
            color: '#212121',
          },
        },
        [
          h(
            'h1',
            {
              style: {
                fontSize: '2rem',
                fontWeight: '600',
                marginBottom: '0.5rem',
                color: '#212121',
              },
            },
            'Design Tokens',
          ),
          h(
            'p',
            {
              style: {
                fontSize: '1.125rem',
                color: '#8e8e8e',
                marginBottom: '3rem',
              },
            },
            'Comprehensive guide to the three-layer design token system used throughout the CO2 Calculator application.',
          ),

          Section('Overview', [
            h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
              'The design token system in this application follows a ',
              h('strong', 'three-layer architecture'),
              ' that separates raw values from semantic meaning and component-specific usage. This approach ensures consistency, maintainability, and scalability across the entire design system.',
            ]),
            h(
              'p',
              { style: { marginBottom: '1rem', fontSize: '1rem' } },
              'Each layer builds upon the previous one, creating a clear hierarchy that makes it easy to understand where values come from and how they should be used.',
            ),
          ]),

          Section('The Three-Layer Architecture', [
            SubSection('Layer 1: Options (Primitives)', [
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Purpose: '),
                'Raw primitive values that define what is available in the design system. These are the foundational building blocks.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'File: '),
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '_options.scss',
                ),
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Visibility: '),
                h(
                  'span',
                  { style: { color: '#dc3545', fontWeight: '600' } },
                  'PRIVATE',
                ),
                ' - These tokens should NOT be used directly in components. They are only referenced by other token files.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Example: '),
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '$tokens-spacing-16',
                ),
                ' = ',
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '1rem',
                ),
              ]),
              CodeBlock(`// ❌ DON'T use options directly in components
.my-component {
  padding: $tokens-spacing-16; // Wrong!
}

// ✅ DO use decisions or components instead
.my-component {
  padding: $spacing-lg; // Correct!
}`),
            ]),

            SubSection('Layer 2: Decisions (Semantic)', [
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Purpose: '),
                'Semantic naming that maps options to design decisions. These tokens provide meaningful names for design choices.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'File: '),
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '_decisions.scss',
                ),
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Visibility: '),
                h(
                  'span',
                  { style: { color: '#28a745', fontWeight: '600' } },
                  'PUBLIC',
                ),
                ' - These are the primary tokens you should use in your components.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Example: '),
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '$spacing-lg',
                ),
                ' = ',
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '$tokens-spacing-16',
                ),
                ' = ',
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '1rem',
                ),
              ]),
              CodeBlock(`// ✅ Use decisions for semantic values
@use 'decisions' as dec;

.my-card {
  background-color: dec.$color-surface;
  color: dec.$color-text;
  padding: dec.$spacing-md;
  border-radius: dec.$radius-default;
  border: 1px solid dec.$color-border;
}`),
            ]),

            SubSection('Layer 3: Components (Specific)', [
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Purpose: '),
                'Component-specific token mappings that use decisions and options to style specific UI elements.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'File: '),
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '_components.scss',
                ),
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Visibility: '),
                h(
                  'span',
                  { style: { color: '#28a745', fontWeight: '600' } },
                  'PUBLIC',
                ),
                ' - Use these when you need component-specific styling values.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Example: '),
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '$button-primary-bg-default',
                ),
                ' = ',
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '#ff0000',
                ),
              ]),
              CodeBlock(`// ✅ Use component tokens for component-specific styling
@use 'components' as comp;

.my-button {
  padding: comp.$button-size-md-padding-y comp.$button-size-md-padding-x;
  background-color: comp.$button-primary-bg-default;
  color: comp.$button-primary-color;
  border-radius: comp.$button-radius;
  
  &:hover {
    background-color: comp.$button-primary-bg-hover;
  }
}`),
            ]),
          ]),

          Section('Why This Architecture?', [
            h('ul', { style: { marginLeft: '1.5rem', lineHeight: '1.8' } }, [
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Flexibility: '),
                'Change "primary" color from red to blue by updating one decision token, and all components update automatically.',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Consistency: '),
                'All components using the same semantic token will always have the same value, preventing design drift.',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Scalability: '),
                'Add new components easily by referencing existing decisions and components tokens.',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Maintainability: '),
                'Changes flow naturally down the hierarchy. Update an option, and all dependent tokens update.',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Developer Experience: '),
                'Clear naming conventions make it obvious which token to use in any situation.',
              ]),
            ]),
          ]),

          Section('How to Use Tokens', [
            SubSection('Importing Tokens', [
              h(
                'p',
                { style: { marginBottom: '1rem', fontSize: '1rem' } },
                'Use SCSS modules (@use) to import the token layers you need:',
              ),
              CodeBlock(`// Import decisions (most common)
@use 'decisions' as dec;

// Import components (for component-specific values)
@use 'components' as comp;

// Import both (common pattern)
@use 'decisions' as dec;
@use 'components' as comp;`),
            ]),

            SubSection('Using Decision Tokens', [
              h(
                'p',
                { style: { marginBottom: '1rem', fontSize: '1rem' } },
                'Use decision tokens for semantic values in your components:',
              ),
              CodeBlock(`@use 'decisions' as dec;

.my-card {
  // Colors
  background-color: dec.$color-surface;
  color: dec.$color-text;
  border: 1px solid dec.$color-border;
  
  // Spacing
  padding: dec.$spacing-md;
  margin-bottom: dec.$spacing-lg;
  
  // Typography
  font-family: dec.$text-font-family;
  font-size: dec.$text-size-base;
  line-height: dec.$text-line-height-base;
  font-weight: dec.$text-weight-medium;
  
  // Border radius
  border-radius: dec.$radius-default;
}`),
            ]),

            SubSection('Using Component Tokens', [
              h(
                'p',
                { style: { marginBottom: '1rem', fontSize: '1rem' } },
                'Use component tokens when you need component-specific styling:',
              ),
              CodeBlock(`@use 'components' as comp;

.my-button {
  // Button-specific tokens
  padding: comp.$button-size-md-padding-y comp.$button-size-md-padding-x;
  background-color: comp.$button-primary-bg-default;
  color: comp.$button-primary-color;
  border-radius: comp.$button-radius;
  font-size: comp.$button-size-md-font-size;
  transition: comp.$button-transition-duration;
  
  &:hover {
    background-color: comp.$button-primary-bg-hover;
  }
  
  &:disabled {
    background-color: comp.$button-disabled-bg;
    color: comp.$button-disabled-color;
  }
}`),
            ]),

            SubSection('Mixing Decision and Component Tokens', [
              h(
                'p',
                { style: { marginBottom: '1rem', fontSize: '1rem' } },
                'You can mix both decision and component tokens as needed:',
              ),
              CodeBlock(`@use 'decisions' as dec;
@use 'components' as comp;

.my-form {
  // Use decision tokens for general styling
  background-color: dec.$color-surface;
  padding: dec.$spacing-lg;
  border-radius: dec.$radius-default;
  
  // Use component tokens for form-specific styling
  .form-field {
    padding: comp.$field-md-padding-y comp.$field-md-padding-x;
    border: comp.$field-border-weight solid comp.$field-border-default;
    border-radius: comp.$field-border-radius;
    font-size: comp.$field-md-font-size;
    
    &:focus {
      border-color: comp.$field-border-focus;
    }
    
    &:disabled {
      background-color: comp.$field-bg-disabled;
      color: comp.$field-color-disabled;
    }
  }
}`),
            ]),
          ]),

          Section('CSS Layer System', [
            h(
              'p',
              { style: { marginBottom: '1rem', fontSize: '1rem' } },
              'The application uses a layer system that controls CSS cascade order. This ensures styles are applied in the correct sequence, preventing specificity conflicts and making the stylesheet predictable.',
            ),
            SubSection('Layer Order', [
              h(
                'p',
                { style: { marginBottom: '1rem', fontSize: '1rem' } },
                'Layers are defined in order of increasing specificity, from generic to specific:',
              ),
              h('ol', { style: { marginLeft: '1.5rem', lineHeight: '1.8' } }, [
                h('li', { style: { marginBottom: '0.5rem' } }, [
                  h('strong', 'reset: '),
                  'CSS resets and normalization (normalize.css)',
                ]),
                h('li', { style: { marginBottom: '0.5rem' } }, [
                  h('strong', 'fonts: '),
                  'Font face declarations and font loading',
                ]),
                h('li', { style: { marginBottom: '0.5rem' } }, [
                  h('strong', 'tokens: '),
                  'CSS custom properties (CSS variables) exported from tokens',
                ]),
                h('li', { style: { marginBottom: '0.5rem' } }, [
                  h('strong', 'quasar-base: '),
                  'Quasar framework base styles (imported from Quasar)',
                ]),
                h('li', { style: { marginBottom: '0.5rem' } }, [
                  h('strong', 'layout: '),
                  'Layout components (body, grid, container, modal)',
                ]),
                h('li', { style: { marginBottom: '0.5rem' } }, [
                  h('strong', 'quasar-overrides: '),
                  'Overrides for Quasar components to match design system',
                ]),
                h('li', { style: { marginBottom: '0.5rem' } }, [
                  h('strong', 'components: '),
                  'Application-specific components (atoms, molecules, organisms, templates)',
                ]),
                h('li', { style: { marginBottom: '0.5rem' } }, [
                  h('strong', 'utilities: '),
                  'Utility classes (spacing, text utilities)',
                ]),
              ]),
              CodeBlock(`// app.scss
@layer reset, fonts, tokens, quasar-base, layout, quasar-overrides, components, utilities;

@layer reset {
  @import './01-reset/normalize';
}

@layer fonts {
  @import './00-fonts/fonts';
}

@layer tokens {
  @import './02-tokens/css-properties';
}

@layer quasar-base {
  @import 'quasar/src/css/index.sass';
}

@layer quasar-overrides {
  @import './05-components/quasar-overrides/q-btn';
  @import './05-components/quasar-overrides/q-table';
  // ... more overrides
}

@layer components {
  @import './05-components/_atoms/icon';
  @import './05-components/_organisms/navigation';
  // ... more components
}

@layer utilities {
  @import './04-utils/spacing';
  @import './04-utils/text';
}`),
            ]),
            SubSection('Why Layers?', [
              h('ul', { style: { marginLeft: '1.5rem', lineHeight: '1.8' } }, [
                h('li', { style: { marginBottom: '0.75rem' } }, [
                  h('strong', 'Predictable Cascade: '),
                  'Layers ensure styles are applied in a specific order, regardless of selector specificity.',
                ]),
                h('li', { style: { marginBottom: '0.75rem' } }, [
                  h('strong', 'No Specificity Wars: '),
                  'You can override Quasar styles without using !important or extremely specific selectors.',
                ]),
                h('li', { style: { marginBottom: '0.75rem' } }, [
                  h('strong', 'Clear Organization: '),
                  'Each layer has a clear purpose, making it easy to find and maintain styles.',
                ]),
                h('li', { style: { marginBottom: '0.75rem' } }, [
                  h('strong', 'Framework Integration: '),
                  'Quasar styles are isolated in their own layer, making overrides safe and predictable.',
                ]),
              ]),
            ]),
          ]),

          Section('Quasar Integration', [
            h(
              'p',
              { style: { marginBottom: '1rem', fontSize: '1rem' } },
              'The application uses Quasar Framework for UI components. To ensure Quasar components match our design system, we use two mechanisms: the Quasar Bridge and Quasar Overrides.',
            ),
            SubSection('Quasar Bridge', [
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Purpose: '),
                'Maps our design tokens to Quasar SCSS variables before Quasar styles are compiled. This allows Quasar components to use our design system values by default.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'File: '),
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '_quasar-bridge.scss',
                ),
              ]),
              h(
                'p',
                { style: { marginBottom: '1rem', fontSize: '1rem' } },
                'The bridge is imported before Quasar styles, ensuring our tokens are available when Quasar compiles:',
              ),
              CodeBlock(`// app.scss
// Map SCSS tokens to Quasar variables BEFORE Quasar is imported
@import './02-tokens/quasar-bridge';

// Now Quasar can use our token values
@layer quasar-base {
  @import 'quasar/src/css/index.sass';
}`),
              h(
                'p',
                { style: { marginBottom: '1rem', fontSize: '1rem' } },
                'Example mappings:',
              ),
              CodeBlock(`// _quasar-bridge.scss
@use 'decisions' as dec;
@use 'components' as comp;
@use 'options' as opt;

// Brand colors
$primary: dec.$color-text;
$accent: dec.$color-primary !default;
$positive: dec.$color-status-success !default;
$negative: dec.$color-status-error !default;

// Spacing
$space-base: dec.$spacing-md !default;
$space-xs: (x: dec.$spacing-xs, y: dec.$spacing-xs) !default;
$space-sm: (x: dec.$spacing-sm, y: dec.$spacing-sm) !default;

// Typography
$body-font-size: dec.$text-size-sm !default;
$typography-font-family: dec.$text-font-family !default;

// Buttons
$button-border-radius: comp.$button-radius !default;
$button-primary-background: comp.$button-primary-bg-default !default;
$button-padding-md: comp.$button-size-md-padding-y comp.$button-size-md-padding-x !default;`),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Benefits: '),
                'Quasar components automatically use our design tokens without any additional styling. For example, all Quasar buttons will use our button tokens by default.',
              ]),
            ]),
            SubSection('Quasar Overrides', [
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Purpose: '),
                'Additional CSS overrides for Quasar components that need custom styling beyond what the bridge provides. These are placed in the quasar-overrides layer, which comes after quasar-base but before components.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Location: '),
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  '05-components/quasar-overrides/',
                ),
              ]),
              h(
                'p',
                { style: { marginBottom: '1rem', fontSize: '1rem' } },
                'Overrides use our design tokens to customize Quasar components:',
              ),
              CodeBlock(`// _q-btn.scss
@use '../../02-tokens' as tokens;

// Override Quasar button styles using our tokens
.q-btn {
  // Use component tokens for button-specific styling
  padding: tokens.$button-size-md-padding-y tokens.$button-size-md-padding-x;
  border-radius: tokens.$button-radius;
  font-size: tokens.$button-size-md-font-size;
  
  // Custom classes for specific button variants
  &.btn-primary {
    background-color: tokens.$button-primary-bg-default;
    color: tokens.$button-primary-color;
  }
  
  &.btn-secondary {
    background-color: tokens.$button-secondary-bg-default;
    border: 1px solid tokens.$button-secondary-border-color;
  }
}`),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'When to Use Overrides: '),
                'Use overrides when you need to customize Quasar components beyond what the bridge provides, such as adding custom classes, modifying specific states, or creating component variants.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Layer Order: '),
                'Overrides are in the quasar-overrides layer, which comes after quasar-base. This ensures overrides take precedence over Quasar defaults without needing !important or high specificity.',
              ]),
            ]),
            SubSection('CSS Custom Properties', [
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'Purpose: '),
                'Export design tokens as CSS custom properties (CSS variables) for use in JavaScript, inline styles, or dynamic styling.',
              ]),
              h('p', { style: { marginBottom: '1rem', fontSize: '1rem' } }, [
                h('strong', 'File: '),
                h(
                  'code',
                  {
                    style: {
                      backgroundColor: '#f5f5f5',
                      padding: '0.2rem 0.4rem',
                      borderRadius: '3px',
                      fontSize: '0.875rem',
                    },
                  },
                  'css-properties.scss',
                ),
              ]),
              CodeBlock(`// css-properties.scss
@use 'decisions' as dec;
@use 'components' as comp;

:root {
  --semantic-color-primary: #{dec.$color-primary};
  --semantic-color-surface: #{dec.$color-surface};
  --semantic-color-text: #{dec.$color-text};
  --semantic-spacing-md: #{dec.$spacing-md};
  --semantic-button-padding-y: #{comp.$button-size-md-padding-y};
  --semantic-button-padding-x: #{comp.$button-size-md-padding-x};
}`),
              h(
                'p',
                { style: { marginBottom: '1rem', fontSize: '1rem' } },
                'These can be used in JavaScript or inline styles:',
              ),
              CodeBlock(`// JavaScript
element.style.setProperty('--custom-color', 'var(--semantic-color-primary)');

// Inline styles
<div style="padding: var(--semantic-spacing-md)">

// CSS
.my-component {
  background-color: var(--semantic-color-surface);
  padding: var(--semantic-spacing-lg);
}`),
            ]),
          ]),

          Section('Best Practices', [
            h('ul', { style: { marginLeft: '1.5rem', lineHeight: '1.8' } }, [
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Never use options directly: '),
                'Always use decisions or components tokens in your component styles.',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Prefer decisions over components: '),
                'Use decision tokens for general styling, and component tokens only when you need component-specific values.',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Use semantic names: '),
                'Choose tokens based on their meaning (e.g., $spacing-md) rather than their value (e.g., $tokens-spacing-12).',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Group related tokens: '),
                'When using multiple tokens, group them logically (colors together, spacing together, etc.).',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Respect layer order: '),
                'Place styles in the appropriate layer. Use quasar-overrides for Quasar customizations, components for app components, and utilities for utility classes.',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Use the bridge first: '),
                'Before creating Quasar overrides, check if the bridge can handle it. Only use overrides when bridge mappings are insufficient.',
              ]),
              h('li', { style: { marginBottom: '0.75rem' } }, [
                h('strong', 'Document custom tokens: '),
                'If you create new component tokens, document them in the component file.',
              ]),
            ]),
          ]),

          Section('Reference Pages', [
            h(
              'p',
              { style: { marginBottom: '1rem', fontSize: '1rem' } },
              'For complete token listings, see the reference pages:',
            ),
            h('ul', { style: { marginLeft: '1.5rem', lineHeight: '1.8' } }, [
              h('li', { style: { marginBottom: '0.5rem' } }, [
                h('strong', 'Options Reference: '),
                'Complete listing of all primitive tokens (for reference only - do not use directly).',
              ]),
              h('li', { style: { marginBottom: '0.5rem' } }, [
                h('strong', 'Decisions Reference: '),
                'Complete listing of all semantic decision tokens (use these in your components).',
              ]),
              h('li', { style: { marginBottom: '0.5rem' } }, [
                h('strong', 'Components Reference: '),
                'Complete listing of all component-specific tokens (use when you need component-specific values).',
              ]),
            ]),
          ]),
        ],
      );
  },
});

// ============================================================================
// REFERENCE PAGES (No explanations, just tables)
// ============================================================================

// eslint-disable-next-line vue/one-component-per-file
const OptionsReference = defineComponent({
  name: 'OptionsReference',
  setup() {
    const TokenRow = (name: string, value: string) => {
      return h('tr', [
        h(
          'td',
          {
            style: {
              padding: '0.75rem',
              fontWeight: '500',
              borderBottom: '1px solid #e6e6e6',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
            },
          },
          name,
        ),
        h(
          'td',
          {
            style: {
              padding: '0.75rem',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              color: '#8e8e8e',
              borderBottom: '1px solid #e6e6e6',
            },
          },
          value,
        ),
      ]);
    };

    const TokenTable = (tokens: Record<string, string>, prefix: string) => {
      return h(
        'table',
        {
          style: {
            width: '100%',
            borderCollapse: 'collapse',
            marginBottom: '2rem',
          },
        },
        [
          h('thead', [
            h('tr', [
              h(
                'th',
                {
                  style: {
                    padding: '0.75rem',
                    textAlign: 'left',
                    fontWeight: '600',
                    borderBottom: '2px solid #e6e6e6',
                    backgroundColor: '#f5f5f5',
                  },
                },
                'Token',
              ),
              h(
                'th',
                {
                  style: {
                    padding: '0.75rem',
                    textAlign: 'left',
                    fontWeight: '600',
                    borderBottom: '2px solid #e6e6e6',
                    backgroundColor: '#f5f5f5',
                  },
                },
                'Value',
              ),
            ]),
          ]),
          h('tbody', [
            ...Object.entries(tokens).map(([key, value]) =>
              TokenRow(`$${prefix}-${key}`, value),
            ),
          ]),
        ],
      );
    };

    const ColorSwatch = (color: string, name: string, value: string) => {
      return h(
        'tr',
        {
          style: {
            borderBottom: '1px solid #e6e6e6',
          },
        },
        [
          h(
            'td',
            {
              style: {
                padding: '0.75rem',
                fontWeight: '500',
                fontFamily: 'monospace',
                fontSize: '0.875rem',
              },
            },
            name,
          ),
          h(
            'td',
            {
              style: {
                padding: '0.75rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
              },
            },
            [
              h('div', {
                style: {
                  width: '40px',
                  height: '40px',
                  backgroundColor: color,
                  border: '1px solid #d5d5d5',
                  borderRadius: '3px',
                  flexShrink: 0,
                },
              }),
              h(
                'span',
                {
                  style: {
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                    color: '#8e8e8e',
                  },
                },
                value,
              ),
            ],
          ),
        ],
      );
    };

    const ColorTable = (
      colors: Record<string, string>,
      prefix: string,
      title: string,
    ) => {
      return h('div', { style: { marginBottom: '2rem' } }, [
        h(
          'h2',
          {
            style: {
              fontSize: '1.5rem',
              fontWeight: '600',
              marginBottom: '1rem',
            },
          },
          title,
        ),
        h(
          'table',
          {
            style: {
              width: '100%',
              borderCollapse: 'collapse',
            },
          },
          [
            h('thead', [
              h('tr', [
                h(
                  'th',
                  {
                    style: {
                      padding: '0.75rem',
                      textAlign: 'left',
                      fontWeight: '600',
                      borderBottom: '2px solid #e6e6e6',
                      backgroundColor: '#f5f5f5',
                    },
                  },
                  'Token',
                ),
                h(
                  'th',
                  {
                    style: {
                      padding: '0.75rem',
                      textAlign: 'left',
                      fontWeight: '600',
                      borderBottom: '2px solid #e6e6e6',
                      backgroundColor: '#f5f5f5',
                    },
                  },
                  'Value',
                ),
              ]),
            ]),
            h('tbody', [
              ...Object.entries(colors).map(([key, value]) =>
                ColorSwatch(value, `$${prefix}-${key}`, value),
              ),
            ]),
          ],
        ),
      ]);
    };

    return () =>
      h(
        'div',
        {
          style: {
            padding: '2rem',
            maxWidth: '1200px',
            margin: '0 auto',
          },
        },
        [
          h(
            'h1',
            {
              style: {
                fontSize: '2rem',
                fontWeight: '600',
                marginBottom: '0.5rem',
              },
            },
            'Options Reference',
          ),
          h(
            'p',
            {
              style: {
                fontSize: '1rem',
                color: '#8e8e8e',
                marginBottom: '2rem',
              },
            },
            'Complete listing of all primitive tokens. These are PRIVATE and should NOT be used directly in components.',
          ),
          TokenTable(optionsTokens.spacing, 'tokens-spacing'),
          TokenTable(optionsTokens.borderRadius, 'tokens-border-radius'),
          h('div', { style: { marginBottom: '2rem' } }, [
            h(
              'h2',
              {
                style: {
                  fontSize: '1.5rem',
                  fontWeight: '600',
                  marginBottom: '1rem',
                },
              },
              'Typography',
            ),
            h(
              'p',
              {
                style: {
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                  color: '#8e8e8e',
                  padding: '0.75rem',
                  backgroundColor: '#f5f5f5',
                  borderRadius: '3px',
                  marginBottom: '1rem',
                },
              },
              `$tokens-typography-font-family-base: ${optionsTokens.typography.fontFamily}`,
            ),
            TokenTable(
              optionsTokens.typography.fontSizes,
              'tokens-typography-font-size',
            ),
            TokenTable(
              optionsTokens.typography.lineHeights,
              'tokens-typography-line-height',
            ),
            TokenTable(
              optionsTokens.typography.fontWeights,
              'tokens-typography-font-weight',
            ),
          ]),
          TokenTable(optionsTokens.iconSizes, 'tokens-icon-size'),
          ColorTable(
            optionsTokens.colors.status,
            'tokens-colors-status',
            'Status Colors',
          ),
          ColorTable(
            optionsTokens.colors.greyScale,
            'tokens-colors-grey-scale-grey',
            'Grey Scale',
          ),
          ColorTable(
            optionsTokens.colors.accent,
            'tokens-colors',
            'Accent Colors',
          ),
          ColorTable(
            optionsTokens.colors.red,
            'tokens-colors-red',
            'Red Colors',
          ),
          ColorTable(
            optionsTokens.colors.base,
            'tokens-colors-base',
            'Base Colors',
          ),
          TokenTable(optionsTokens.layout, 'tokens-layout'),
          TokenTable(optionsTokens.transitions, 'tokens-transitions'),
          h('div', { style: { marginBottom: '2rem' } }, [
            h(
              'h2',
              {
                style: {
                  fontSize: '1.5rem',
                  fontWeight: '600',
                  marginBottom: '1rem',
                },
              },
              'Box Shadow',
            ),
            h(
              'p',
              {
                style: {
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                  color: '#8e8e8e',
                  padding: '0.75rem',
                  backgroundColor: '#f5f5f5',
                  borderRadius: '3px',
                },
              },
              `$tokens-box-shadow: ${optionsTokens.boxShadow}`,
            ),
          ]),
          TokenTable(optionsTokens.zIndex, 'tokens-z-index'),
        ],
      );
  },
});

// eslint-disable-next-line vue/one-component-per-file
const DecisionsReference = defineComponent({
  name: 'DecisionsReference',
  setup() {
    const TokenRow = (name: string, value: string) => {
      return h('tr', [
        h(
          'td',
          {
            style: {
              padding: '0.75rem',
              fontWeight: '500',
              borderBottom: '1px solid #e6e6e6',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
            },
          },
          name,
        ),
        h(
          'td',
          {
            style: {
              padding: '0.75rem',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              color: '#8e8e8e',
              borderBottom: '1px solid #e6e6e6',
            },
          },
          value,
        ),
      ]);
    };

    const TokenTable = (tokens: Record<string, string>, prefix: string) => {
      return h(
        'table',
        {
          style: {
            width: '100%',
            borderCollapse: 'collapse',
            marginBottom: '2rem',
          },
        },
        [
          h('thead', [
            h('tr', [
              h(
                'th',
                {
                  style: {
                    padding: '0.75rem',
                    textAlign: 'left',
                    fontWeight: '600',
                    borderBottom: '2px solid #e6e6e6',
                    backgroundColor: '#f5f5f5',
                  },
                },
                'Token',
              ),
              h(
                'th',
                {
                  style: {
                    padding: '0.75rem',
                    textAlign: 'left',
                    fontWeight: '600',
                    borderBottom: '2px solid #e6e6e6',
                    backgroundColor: '#f5f5f5',
                  },
                },
                'Value',
              ),
            ]),
          ]),
          h('tbody', [
            ...Object.entries(tokens).map(([key, value]) =>
              TokenRow(`$${prefix}-${key}`, value),
            ),
          ]),
        ],
      );
    };

    const ColorSwatch = (color: string, name: string, value: string) => {
      return h(
        'tr',
        {
          style: {
            borderBottom: '1px solid #e6e6e6',
          },
        },
        [
          h(
            'td',
            {
              style: {
                padding: '0.75rem',
                fontWeight: '500',
                fontFamily: 'monospace',
                fontSize: '0.875rem',
              },
            },
            name,
          ),
          h(
            'td',
            {
              style: {
                padding: '0.75rem',
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
              },
            },
            [
              h('div', {
                style: {
                  width: '40px',
                  height: '40px',
                  backgroundColor: color,
                  border: '1px solid #d5d5d5',
                  borderRadius: '3px',
                  flexShrink: 0,
                },
              }),
              h(
                'span',
                {
                  style: {
                    fontFamily: 'monospace',
                    fontSize: '0.875rem',
                    color: '#8e8e8e',
                  },
                },
                value,
              ),
            ],
          ),
        ],
      );
    };

    const ColorTable = (
      colors: Record<string, string>,
      prefix: string,
      title: string,
    ) => {
      return h('div', { style: { marginBottom: '2rem' } }, [
        h(
          'h2',
          {
            style: {
              fontSize: '1.5rem',
              fontWeight: '600',
              marginBottom: '1rem',
            },
          },
          title,
        ),
        h(
          'table',
          {
            style: {
              width: '100%',
              borderCollapse: 'collapse',
            },
          },
          [
            h('thead', [
              h('tr', [
                h(
                  'th',
                  {
                    style: {
                      padding: '0.75rem',
                      textAlign: 'left',
                      fontWeight: '600',
                      borderBottom: '2px solid #e6e6e6',
                      backgroundColor: '#f5f5f5',
                    },
                  },
                  'Token',
                ),
                h(
                  'th',
                  {
                    style: {
                      padding: '0.75rem',
                      textAlign: 'left',
                      fontWeight: '600',
                      borderBottom: '2px solid #e6e6e6',
                      backgroundColor: '#f5f5f5',
                    },
                  },
                  'Value',
                ),
              ]),
            ]),
            h('tbody', [
              ...Object.entries(colors).map(([key, value]) =>
                ColorSwatch(value, `$${prefix}-${key}`, value),
              ),
            ]),
          ],
        ),
      ]);
    };

    return () =>
      h(
        'div',
        {
          style: {
            padding: '2rem',
            maxWidth: '1200px',
            margin: '0 auto',
          },
        },
        [
          h(
            'h1',
            {
              style: {
                fontSize: '2rem',
                fontWeight: '600',
                marginBottom: '0.5rem',
              },
            },
            'Decisions Reference',
          ),
          h(
            'p',
            {
              style: {
                fontSize: '1rem',
                color: '#8e8e8e',
                marginBottom: '2rem',
              },
            },
            'Complete listing of all semantic decision tokens. Use these in your components.',
          ),
          ColorTable(decisionsTokens.colors.brand, 'color', 'Brand Colors'),
          ColorTable(
            decisionsTokens.colors.semantic,
            'color',
            'Semantic Colors',
          ),
          ColorTable(
            decisionsTokens.colors.status,
            'color-status',
            'Status Colors',
          ),
          TokenTable(decisionsTokens.spacing, 'spacing'),
          TokenTable(decisionsTokens.borderRadius, 'radius'),
          h('div', { style: { marginBottom: '2rem' } }, [
            h(
              'h2',
              {
                style: {
                  fontSize: '1.5rem',
                  fontWeight: '600',
                  marginBottom: '1rem',
                },
              },
              'Typography',
            ),
            h(
              'p',
              {
                style: {
                  fontFamily: 'monospace',
                  fontSize: '0.875rem',
                  color: '#8e8e8e',
                  padding: '0.75rem',
                  backgroundColor: '#f5f5f5',
                  borderRadius: '3px',
                  marginBottom: '1rem',
                },
              },
              `$text-font-family: ${decisionsTokens.typography.fontFamily}`,
            ),
            TokenTable(decisionsTokens.typography.fontSizes, 'text-size'),
            TokenTable(
              decisionsTokens.typography.lineHeights,
              'text-line-height',
            ),
            TokenTable(decisionsTokens.typography.fontWeights, 'text-weight'),
          ]),
          TokenTable(decisionsTokens.layout, 'layout'),
          TokenTable(decisionsTokens.modal, 'modal-width'),
          TokenTable(decisionsTokens.icons, 'icon-size'),
          TokenTable(decisionsTokens.tooltip, 'tooltip'),
        ],
      );
  },
});

// eslint-disable-next-line vue/one-component-per-file
const ComponentsReference = defineComponent({
  name: 'ComponentsReference',
  setup() {
    const TokenRow = (name: string, value: string) => {
      return h('tr', [
        h(
          'td',
          {
            style: {
              padding: '0.75rem',
              fontWeight: '500',
              borderBottom: '1px solid #e6e6e6',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
            },
          },
          name,
        ),
        h(
          'td',
          {
            style: {
              padding: '0.75rem',
              fontFamily: 'monospace',
              fontSize: '0.875rem',
              color: '#8e8e8e',
              borderBottom: '1px solid #e6e6e6',
            },
          },
          value,
        ),
      ]);
    };

    const TokenTable = (tokens: Record<string, string>, prefix: string) => {
      return h(
        'table',
        {
          style: {
            width: '100%',
            borderCollapse: 'collapse',
            marginBottom: '2rem',
          },
        },
        [
          h('thead', [
            h('tr', [
              h(
                'th',
                {
                  style: {
                    padding: '0.75rem',
                    textAlign: 'left',
                    fontWeight: '600',
                    borderBottom: '2px solid #e6e6e6',
                    backgroundColor: '#f5f5f5',
                  },
                },
                'Token',
              ),
              h(
                'th',
                {
                  style: {
                    padding: '0.75rem',
                    textAlign: 'left',
                    fontWeight: '600',
                    borderBottom: '2px solid #e6e6e6',
                    backgroundColor: '#f5f5f5',
                  },
                },
                'Value',
              ),
            ]),
          ]),
          h('tbody', [
            ...Object.entries(tokens).map(([key, value]) =>
              TokenRow(`$${prefix}-${key}`, value),
            ),
          ]),
        ],
      );
    };

    return () =>
      h(
        'div',
        {
          style: {
            padding: '2rem',
            maxWidth: '1200px',
            margin: '0 auto',
          },
        },
        [
          h(
            'h1',
            {
              style: {
                fontSize: '2rem',
                fontWeight: '600',
                marginBottom: '0.5rem',
              },
            },
            'Components Reference',
          ),
          h(
            'p',
            {
              style: {
                fontSize: '1rem',
                color: '#8e8e8e',
                marginBottom: '2rem',
              },
            },
            'Complete listing of all component-specific tokens. Use these when you need component-specific styling values.',
          ),
          ...Object.entries(componentTokens).map(([componentName, tokens]) =>
            h(
              'div',
              {
                style: {
                  marginBottom: '2rem',
                },
                key: componentName,
              },
              [
                h(
                  'h2',
                  {
                    style: {
                      fontSize: '1.5rem',
                      fontWeight: '600',
                      marginBottom: '1rem',
                      textTransform: 'capitalize',
                    },
                  },
                  componentName.replace(/([A-Z])/g, ' $1').trim(),
                ),
                TokenTable(tokens, componentName),
              ],
            ),
          ),
        ],
      );
  },
});

// ============================================================================
// STORYBOOK CONFIGURATION
// ============================================================================

const meta = {
  title: 'Documentation/Design Tokens',
  component: DesignTokensDocumentation,
  parameters: {
    layout: 'fullscreen',
    docs: {
      description: {
        component:
          'Comprehensive documentation of all design tokens organized in a three-layer hierarchy: Options, Decisions, and Components.',
      },
    },
  },
} satisfies Meta<typeof DesignTokensDocumentation>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Design Tokens Documentation
 *
 * Comprehensive guide to the three-layer design token system used throughout the application.
 * This page explains the architecture, how to use tokens, and best practices.
 */
export const Documentation: Story = {
  parameters: {
    docsOnly: true,
  },
  render: () => ({
    components: { DesignTokensDocumentation },
    template: '<DesignTokensDocumentation />',
  }),
};

/**
 * Options Reference
 *
 * Complete listing of all primitive tokens (Options layer).
 * These tokens are PRIVATE and should NOT be used directly in components.
 * They are only referenced by other token files.
 */
export const Options: Story = {
  parameters: {
    layout: 'fullscreen',
    docsOnly: true,
  },
  render: () => ({
    components: { OptionsReference },
    template: '<OptionsReference />',
  }),
};

/**
 * Decisions Reference
 *
 * Complete listing of all semantic decision tokens (Decisions layer).
 * These are the primary tokens you should use in your components.
 */
export const Decisions: Story = {
  parameters: {
    layout: 'fullscreen',
    docsOnly: true,
  },
  render: () => ({
    components: { DecisionsReference },
    template: '<DecisionsReference />',
  }),
};

/**
 * Components Reference
 *
 * Complete listing of all component-specific tokens (Components layer).
 * Use these when you need component-specific styling values.
 */
export const Components: Story = {
  parameters: {
    layout: 'fullscreen',
    docsOnly: true,
  },
  render: () => ({
    components: { ComponentsReference },
    template: '<ComponentsReference />',
  }),
};
