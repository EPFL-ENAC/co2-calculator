import type { RouteParams } from 'vue-router';
import { LOCALE_MAP, Language, Locale } from 'src/constant/languages';
import { i18n } from 'src/boot/i18n';

// Maps route language codes (en, fr) to i18n locale codes (en-US, fr-CH)
export const routeLanguageToLocale = (language: Language): Locale => {
  return LOCALE_MAP[language];
};

/**
 * The active UI language as a route param (`en` / `fr`). Derived from the i18n
 * locale, which itself resolves cookie → browser → default in the i18n boot, so
 * this is the single fallback used everywhere instead of a hard-coded 'en'.
 */
export const currentLanguage = (): Language =>
  i18n.global.locale.value.split('-')[0] as Language;

/**
 * Resolve the language for a navigation target: the URL param when present,
 * otherwise the active UI language. Centralises locale resolution so redirects
 * stay deterministic and no fallback locale is hard-coded inline.
 */
export const resolveLanguage = (route: { params: RouteParams }): Language => {
  const fromUrl = route.params.language;
  if (typeof fromUrl === 'string' && fromUrl.length > 0) {
    return fromUrl as Language;
  }
  return currentLanguage();
};
