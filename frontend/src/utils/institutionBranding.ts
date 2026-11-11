/**
 * Applies the institution branding that the stylesheet and index.html cannot
 * know at build time (#500): accent colors and page title. The same
 * bundle ships to every institution, so these come from the runtime
 * configuration and `src/boot/institution.ts` applies them at startup.
 */

export interface InstitutionBranding {
  name: string;
  accentColor: string;
}

const HEX_COLOR = /^#[0-9a-f]{6}$/i;

/**
 * CSS custom properties behind the accent tokens of
 * src/css/02-tokens/_options.scss. No configured color returns nothing, and
 * the tokens keep their EPFL fallback. One configured color sets the accent
 * and derives its three shades, so an institution configures a single value.
 */
export function accentCssProperties(
  accentColor: string,
): Record<string, string> {
  if (!accentColor) return {};
  // Only #rrggbb is accepted: a typo stops the app at startup, it does not
  // render a page with no accent color.
  if (!HEX_COLOR.test(accentColor)) {
    throw new Error(
      `APP_INSTITUTION_ACCENT_COLOR must be #rrggbb, got "${accentColor}"`,
    );
  }
  return {
    '--institution-accent': accentColor,
    '--institution-accent-hover': `color-mix(in srgb, ${accentColor} 75%, black)`,
    '--institution-accent-highlight': `color-mix(in srgb, ${accentColor} 8%, white)`,
    '--institution-accent-highlight-strong': `color-mix(in srgb, ${accentColor} 25%, white)`,
  };
}

export function applyInstitutionBranding(branding: InstitutionBranding): void {
  const root = document.documentElement;
  for (const [property, color] of Object.entries(
    accentCssProperties(branding.accentColor),
  )) {
    root.style.setProperty(property, color);
  }

  document.title = `${branding.name} CO2 Calculator`;
}
