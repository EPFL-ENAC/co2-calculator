/**
 * Applies the institution branding that index.html cannot know at build time
 * (#500): the page title. The same bundle ships to every institution, so the
 * name comes from the runtime configuration and `src/boot/institution.ts`
 * applies it at startup.
 */

export interface InstitutionBranding {
  name: string;
}

export function applyInstitutionBranding(branding: InstitutionBranding): void {
  document.title = `${branding.name} CO2 Calculator`;
}
