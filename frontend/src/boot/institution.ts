import { defineBoot } from '#q-app';
import { runtimeConfig } from '@/config/runtime';
import { requiredConfigError } from '@/config/requiredConfig';
import { applyInstitutionBranding } from '@/utils/institutionBranding';
import { applyTheme, parseThemeEnv } from '@/utils/institutionTheme';

// First boot file (#500). It stops the startup when a required variable or
// the theme is wrong, and writes the reason on the page so an operator sees
// it without a console. The theme must be in place before the first
// component renders, or the page flashes unstyled colors.
function stopStartup(message: string): never {
  document.body.textContent = message;
  throw new Error(message);
}

// theme.env is a static file of the mounted assets folder, not an API call,
// so it does not go through the ky client.
async function loadTheme(): Promise<Record<string, string>> {
  const response = await fetch('/institution/theme.env', { cache: 'no-cache' });
  if (!response.ok) {
    stopStartup(`/institution/theme.env answered ${response.status}`);
  }
  try {
    return parseThemeEnv(await response.text());
  } catch (error: unknown) {
    return stopStartup(error instanceof Error ? error.message : String(error));
  }
}

export default defineBoot(async () => {
  const configError = requiredConfigError(runtimeConfig);
  if (configError !== null) stopStartup(configError);
  applyTheme(document.documentElement, await loadTheme());
  applyInstitutionBranding(runtimeConfig.institution);
});
