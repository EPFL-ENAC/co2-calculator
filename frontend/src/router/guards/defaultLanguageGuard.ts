import { RouteLocationNormalized } from 'vue-router';
import { LOCALE_MAP, Language } from 'src/constant/languages';
import { Cookies } from 'quasar';

import messages from 'src/i18n';

const LOCALE_COOKIE_KEY = 'locale';
const LOCALE_COOKIE_EXPIRE_DAYS = 30;
const LOCALE_COOKIE_PATH = '/';

import { i18n } from 'src/boot/i18n';
import { ROUTES_WITHOUT_LANGUAGE } from '../routes';

export type MessageLanguages = keyof typeof messages;

export async function defaultLanguageGuard(to: RouteLocationNormalized) {
  if (ROUTES_WITHOUT_LANGUAGE.includes(to.name as string)) {
    // Initial load, no need to redirect
    return true;
  }
  // If no language in URL, redirect with current locale
  const toLang = to.params.language as string;
  if (!toLang && !ROUTES_WITHOUT_LANGUAGE.includes(to.name as string)) {
    // determine current language from i18n locale (default was set from cookie or browser in i18n boot)
    const currentLang = i18n.global.locale.value.split('-')[0] as Language;

    // Redirect to same route with language param
    return {
      name: to.name,
      params: { ...to.params, language: currentLang },
      query: to.query,
    };
  }
  // Proceed to the next route
  return true;
}

export async function setLanguageCookieGuard(
  to: RouteLocationNormalized,
  _from: RouteLocationNormalized,
) {
  if (ROUTES_WITHOUT_LANGUAGE.includes(to.name as string)) {
    // Initial load, no need to redirect
    return true;
  }
  const toLang = to.params.language as string;
  const fromLang = _from.params.language as string;

  // If language changed, update locale and cookie
  if (toLang !== fromLang) {
    const newLocale = LOCALE_MAP[toLang as Language] as MessageLanguages;
    i18n.global.locale.value = newLocale;
    Cookies.set(LOCALE_COOKIE_KEY, newLocale, {
      expires: LOCALE_COOKIE_EXPIRE_DAYS,
      path: LOCALE_COOKIE_PATH,
    });
  }
  return true;
}
