import { defineBoot } from '#q-app';
import { runtimeConfig } from '@/config/runtime';
import { requiredConfigError } from '@/config/requiredConfig';
import { applyInstitutionBranding } from '@/utils/institutionBranding';

// First boot file. It stops the startup when a required variable is missing,
// and writes the reason on the page so an operator sees it without a console.
// The accent colors must be in place before the first component renders, or
// the page flashes the default color.
export default defineBoot(() => {
  const configError = requiredConfigError(runtimeConfig);
  if (configError !== null) {
    document.body.textContent = configError;
    throw new Error(configError);
  }
  applyInstitutionBranding(runtimeConfig.institution);
});
