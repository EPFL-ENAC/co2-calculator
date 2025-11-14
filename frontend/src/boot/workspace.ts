import { boot } from 'quasar/wrappers';
import { createI18n } from 'vue-i18n';
import { Cookies } from 'quasar';

const LOCALE_COOKIE_KEY = 'locale';
const LOCALE_COOKIE_EXPIRE_DAYS = 30;
const LOCALE_COOKIE_PATH = '/';
