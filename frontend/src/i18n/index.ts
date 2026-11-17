import type { MessageFunction } from 'vue-i18n';
import { runtimeConfig } from '@/config/runtime';
import { LOCALE_MAP, type Locale } from '@/constant/languages';
import { fillPlaceholders } from '@/utils/i18nPlaceholders';

type Message = string | MessageFunction<string>;
/** One text file, reduced to one language by build/i18n-locale.mjs. */
export type TextModule = Record<string, Message>;
export type Messages = Record<string, Message>;

// One chunk per language: a visitor downloads only the texts they read.
const LOCALE_CHUNKS: Record<Locale, () => Promise<Record<string, TextModule>>> =
  {
    [LOCALE_MAP.en]: async () => (await import('./locales/en')).default,
    [LOCALE_MAP.fr]: async () => (await import('./locales/fr')).default,
  };

const { institution } = runtimeConfig;

// Institution values the texts name through %placeholder% tokens (#3244).
// The same bundle serves every institution, so the values arrive at startup.
// Only the strategy page differs per language.
const SHARED_PLACEHOLDERS: Record<string, string> = {
  institution: institution.name,
  institution_fr_de: institution.nameFrDe,
  institution_fr_a: institution.nameFrA,
  institutional_id: institution.institutionalIdLabel,
  contact_email: institution.contactEmail,
  user_doc_url: institution.userDocUrl,
  backoffice_doc_url: institution.backofficeDocUrl,
};
const PLACEHOLDERS: Record<Locale, Record<string, string>> = {
  [LOCALE_MAP.en]: {
    ...SHARED_PLACEHOLDERS,
    strategy_url: institution.strategyUrlEn,
  },
  [LOCALE_MAP.fr]: {
    ...SHARED_PLACEHOLDERS,
    strategy_url: institution.strategyUrlFr,
  },
};

/** Download the texts of one language and fill their placeholders. */
export const loadMessages = async (locale: Locale): Promise<Messages> => {
  const messages: Messages = {};
  for (const texts of Object.values(await LOCALE_CHUNKS[locale]())) {
    for (const [key, message] of Object.entries(texts)) {
      // A few messages are vue-i18n message functions (common.ts); they
      // build their own text and hold no placeholders.
      messages[key] =
        typeof message === 'string'
          ? fillPlaceholders(message, PLACEHOLDERS[locale], key)
          : message;
    }
  }
  return messages;
};
