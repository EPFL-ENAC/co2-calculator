import { defineBoot } from '#q-app';
import { runtimeConfig } from '@/config/runtime';
import { applyInstitutionBranding } from '@/utils/institutionBranding';

// First boot file: the accent colors must be in place before the first
// component renders, or the page flashes the default color.
export default defineBoot(() => {
  applyInstitutionBranding(runtimeConfig.institution);
});
