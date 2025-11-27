import { boot } from 'quasar/wrappers';
import { createI18n } from 'vue-i18n';
import { Cookies } from 'quasar';
import { LOCALE_MAP, Language } from 'src/constant/languages';
import messages from 'src/i18n';

const LOCALE_COOKIE_KEY = 'locale';

export type MessageLanguages = keyof typeof messages;
// Type-define 'en-US' as the master schema for the resource
export type MessageSchema = (typeof messages)['en-US'];

// See https://vue-i18n.intlify.dev/guide/advanced/typescript.html#global-resource-schema-type-definition

declare module 'vue-i18n' {
  // define the locale messages schema
  export interface DefineLocaleMessage extends MessageSchema {
    title: string;
  }

  // define the datetime format schema
  export interface DefineDateTimeFormat {
    short: Intl.DateTimeFormatOptions;
    long: Intl.DateTimeFormatOptions;
  }

  // define the number format schema
  export interface DefineNumberFormat {
    currency: Intl.NumberFormatOptions;
  }
}

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
});

export default boot(({ app }) => {
  app.use(i18n);
});
