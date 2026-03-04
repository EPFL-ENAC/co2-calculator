import { boot } from 'quasar/wrappers';
import { createI18n } from 'vue-i18n';
import { Cookies } from 'quasar';
import { LOCALE_MAP, Language } from 'src/constant/languages';
import messages from 'src/i18n';
import { nOrDash } from 'src/utils/number';

const LOCALE_COOKIE_KEY = 'locale';

export type MessageLanguages = keyof typeof messages;

// 1. Define the schema
export type MessageSchema = (typeof messages)['en-US'];

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

const numberFormats = {
  'en-US': defaultFormat,
  'de-CH': defaultFormat,
  'fr-CH': defaultFormat,
  // Add other locales as needed, all using the same config
};

// Detect browser language and find matching locale
const getBrowserLocale = (): MessageLanguages => {
  const browserLang = navigator.language.split('-')[0]; // 'en-US' → 'en'
  return LOCALE_MAP[browserLang as Language] ?? LOCALE_MAP.en;
};

const DEFAULT_LOCALE = getBrowserLocale();

// Create i18n instance
export const i18n = createI18n({
  locale:
    (Cookies.get(LOCALE_COOKIE_KEY) as MessageLanguages) || DEFAULT_LOCALE,
  legacy: false,
  messages,
  numberFormats,
  // Show i18n warnings only in dev
  missingWarn: import.meta.env.DEV,
  fallbackWarn: import.meta.env.DEV,
});

export default boot(({ app }) => {
  app.use(i18n);
  app.config.globalProperties.$nOrDash = nOrDash;
});
