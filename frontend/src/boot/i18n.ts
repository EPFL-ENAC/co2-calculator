import { defineBoot } from '#q-app';
import { createI18n } from 'vue-i18n';
import { Cookies } from 'quasar';
import { LANGUAGES, LOCALE_MAP, type Locale } from '@/constant/languages';
import { loadMessages } from '@/i18n';
import {
  nOrDash,
  formatTonnesCO2,
  formatKgCO2,
  formatFTE,
} from '@/utils/number';

const LOCALE_COOKIE_KEY = 'locale';

declare module 'vue-i18n' {
  export interface DefineLocaleMessage {
    [key: string]: string | DefineLocaleMessage;
  }
  export interface DefineDateTimeFormat {
    short: Intl.DateTimeFormatOptions;
    long: Intl.DateTimeFormatOptions;
  }

  export interface DefineNumberFormat {
    currency: Intl.NumberFormatOptions;
    decimal: Intl.NumberFormatOptions;
    percent: Intl.NumberFormatOptions;
  }
}

const defaultFormat: { [key: string]: Intl.NumberFormatOptions } = {
  currency: {
    style: 'currency',
    currency: 'CHF',
    notation: 'standard',
    useGrouping: true,
    currencyDisplay: 'symbol',
  },
  decimal: {
    style: 'decimal',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
    useGrouping: true,
  },
  percent: {
    style: 'percent',
    useGrouping: false,
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  },
};

const defaultDateTimeFormat: { [key: string]: Intl.DateTimeFormatOptions } = {
  short: {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  },
  long: {
    year: '2-digit',
    month: '2-digit',
    day: '2-digit',
    hour: 'numeric',
    minute: 'numeric',
    timeZoneName: 'shortOffset',
  },
};

const numberFormats = {
  'en-US': defaultFormat,
  'de-CH': defaultFormat,
  'fr-CH': defaultFormat,
  // Add other locales as needed, all using the same config
};

const datetimeFormats = {
  'en-US': defaultDateTimeFormat,
  'de-CH': defaultDateTimeFormat,
  'fr-CH': defaultDateTimeFormat,
  // Add other locales as needed, all using the same config
};

const localeOf = (language: string | undefined): Locale | undefined => {
  const known = LANGUAGES.find((candidate) => candidate === language);
  return known === undefined ? undefined : LOCALE_MAP[known];
};

// The language in the URL wins, so the first screen downloads one language
// only; then the cookie, then the browser language.
const getInitialLocale = (): Locale => {
  const cookie = Cookies.get(LOCALE_COOKIE_KEY);
  return (
    localeOf(window.location.pathname.split('/')[1]) ??
    Object.values(LOCALE_MAP).find((locale) => locale === cookie) ??
    localeOf(navigator.language.split('-')[0]) ??
    LOCALE_MAP.en
  );
};

const initialLocale = getInitialLocale();

// Create i18n instance. It starts without texts: setLocale downloads them.
export const i18n = createI18n({
  locale: initialLocale,
  legacy: false,
  numberFormats,
  datetimeFormats,
  // Show i18n warnings only in dev
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
});

/** Download the texts of a language if needed, then switch to it. */
export const setLocale = async (locale: Locale): Promise<void> => {
  if (!i18n.global.availableLocales.includes(locale)) {
    i18n.global.setLocaleMessage(locale, await loadMessages(locale));
  }
  i18n.global.locale.value = locale;
};

// Started at import, not in the boot function: the texts download while the
// other boot files run.
const initialTexts = setLocale(initialLocale);

export default defineBoot(async ({ app }) => {
  // The first screen must not draw before its texts are there.
  await initialTexts;
  app.use(i18n);
  app.config.globalProperties.$nOrDash = nOrDash;
  app.config.globalProperties.$formatTonnesCO2 = formatTonnesCO2;
  app.config.globalProperties.$formatKgCO2 = formatKgCO2;
  app.config.globalProperties.$formatFTE = formatFTE;
});
