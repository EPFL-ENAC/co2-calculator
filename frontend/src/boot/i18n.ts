import { boot } from 'quasar/wrappers';
import { createI18n } from 'vue-i18n';
import { Cookies } from 'quasar';
import { LOCALE_MAP, LocaleMapKey } from 'src/constant/languages';
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
  return (
    browserLang in LOCALE_MAP
      ? LOCALE_MAP[browserLang as LocaleMapKey]
      : LOCALE_MAP.en
  ) as MessageLanguages;
};

const DEFAULT_LOCALE = getBrowserLocale();

// Create i18n instance
export const i18n = createI18n({
  locale:
    (Cookies.get(LOCALE_COOKIE_KEY) as MessageLanguages) || DEFAULT_LOCALE,
  legacy: false,
  messages,
});

export default boot(({ app, router }) => {
  app.use(i18n);

  // Router hook to change locale based on route param or cookie
  router.beforeEach((to) => {
    // Get language from route param or cookie
    const routeLang = to.params.language as string;
    const cookieLocale = Cookies.get(LOCALE_COOKIE_KEY) as MessageLanguages;

    // Determine new locale
    const newLocale = (
      routeLang in LOCALE_MAP
        ? LOCALE_MAP[routeLang as LocaleMapKey]
        : cookieLocale || DEFAULT_LOCALE
    ) as MessageLanguages;

    // Update i18n locale and cookie if changed
    if (i18n.global.locale.value !== newLocale) {
      i18n.global.locale.value = newLocale;
      Cookies.set(LOCALE_COOKIE_KEY, newLocale, { expires: 30, path: '/' });
    }
  });
});
