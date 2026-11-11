/**
 * Institution theme (#500). The assets folder holds theme.env, one
 * `token=value` line per theme token, `#` for comments. Each token sets the
 * --theme-<token> CSS custom property that the SCSS tokens read
 * (src/css/02-tokens/_options.scss). A token left out keeps the base design,
 * except the accent, which the file must set.
 */

// Every --theme-* property of _options.scss. tests/unit/institution-theme.spec.ts
// keeps this list and the stylesheet in step.
export const THEME_TOKENS = [
  'border-radius-generic-border-radius',
  'border-radius-generic-border-radius-px',
  'border-radius-full-border-radius',
  'border-radius-lg-border-radius',
  'colors-status-green',
  'colors-status-red',
  'colors-status-yellow',
  'colors-grey-scale-grey-100',
  'colors-grey-scale-grey-200',
  'colors-grey-scale-grey-300',
  'colors-grey-scale-grey-400',
  'colors-grey-scale-grey-500',
  'colors-grey-scale-grey-600',
  'colors-leman',
  'colors-canard',
  'colors-accent',
  'colors-accent-hover',
  'colors-base-black',
  'colors-base-white',
  'colors-accent-highlight',
  'colors-accent-highlight-strong',
  'colors-validated-highlight',
] as const;

export const REQUIRED_THEME_TOKENS = ['colors-accent'] as const;

const KNOWN = new Set<string>(THEME_TOKENS);

/** Parse theme.env. A wrong line, an unknown token or a missing required
 * token throws, so a typo stops the startup instead of a silent default. */
export function parseThemeEnv(text: string): Record<string, string> {
  const theme: Record<string, string> = {};
  text.split(/\r?\n/).forEach((raw, index) => {
    const line = raw.trim();
    if (line === '' || line.startsWith('#')) return;
    const separator = line.indexOf('=');
    const token = line.slice(0, separator).trim();
    const value = line.slice(separator + 1).trim();
    if (separator < 1 || value === '') {
      throw new Error(`theme.env line ${index + 1}: expected token=value`);
    }
    if (!KNOWN.has(token)) {
      throw new Error(`theme.env line ${index + 1}: unknown token "${token}"`);
    }
    theme[token] = value;
  });
  const missing = REQUIRED_THEME_TOKENS.filter((token) => !(token in theme));
  if (missing.length > 0) {
    throw new Error(`theme.env must set ${missing.join(', ')}`);
  }
  return theme;
}

export function applyTheme(root: HTMLElement, theme: Record<string, string>) {
  for (const [token, value] of Object.entries(theme)) {
    root.style.setProperty(`--theme-${token}`, value);
  }
}
