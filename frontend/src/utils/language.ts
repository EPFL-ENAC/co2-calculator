import type { Language } from 'src/types';

export type Locale = 'en-US' | 'fr-CH';

/**
 * Maps route language codes (en, fr) to i18n locale codes (en-US, fr-CH)
 */
export const routeLanguageToLocale = (language: Language): Locale => {
  const languageMap: Record<Language, Locale> = {
    en: 'en-US',
    fr: 'fr-CH',
  };
  return languageMap[language] || 'en-US';
};

/**
 * Gets the current language from route params or defaults to 'en'
 */
export const getCurrentLanguage = (routeParams: {
  language: Language;
}): Language => {
  return routeParams.language || 'en';
};
