import { boot } from 'quasar/wrappers';
import { Cookies } from 'quasar';
import { LOCALE_MAP, LocaleMapKey } from 'src/constant/languages';

const LOCALE_COOKIE_KEY = 'locale';

export default boot(({ router, app }) => {
  const i18n = app.config.globalProperties.$i18n;

  router.beforeEach((to) => {
    const routeLang = to.params.language as string | undefined;
    const localeValues = Object.values(LOCALE_MAP) as string[];
    let newLocale: string;

    if (routeLang && routeLang in LOCALE_MAP) {
      // Priority 1: Use language from URL
      newLocale = LOCALE_MAP[routeLang as LocaleMapKey];
    } else {
      // Priority 2: Check cookie for saved language preference
      const cookieLocale = Cookies.get(LOCALE_COOKIE_KEY);
      if (cookieLocale && localeValues.includes(cookieLocale)) {
        newLocale = cookieLocale;
      } else {
        // Priority 3: Fall back to default locale
        newLocale = LOCALE_MAP.en;
      }
    }

    // Update i18n locale
    i18n.locale = newLocale;

    // Persist locale to cookie (expires in 1 month)
    Cookies.set(LOCALE_COOKIE_KEY, newLocale, {
      expires: 30,
      path: '/',
    });
  });
});
