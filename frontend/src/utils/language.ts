import { LOCALE_MAP } from 'src/constant/languages';
import type { Language } from 'src/types';

export type Locale = (typeof LOCALE_MAP)[Language];

// Maps route language codes (en, fr) to i18n locale codes (en-US, fr-CH)
export const routeLanguageToLocale = (language: Language): Locale => {
  return LOCALE_MAP[language];
};

// Gets the current language from route params or defaults to 'en'
export const getCurrentLanguage = (routeParams: {
  language: Language;
}): Language => {
  return routeParams.language;
};
