import { runtimeConfig } from '@/config/runtime';
import { fillPlaceholders } from '@/utils/i18nPlaceholders';

type TranslationModule = {
  [key: string]: {
    en: string;
    fr: string;
  };
};

// Load all .ts files in the current directory eagerly
const modules = import.meta.glob<TranslationModule>('./*.ts', { eager: true });

type Lang = 'en' | 'fr';

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
const PLACEHOLDERS: Record<Lang, Record<string, string>> = {
  en: { ...SHARED_PLACEHOLDERS, strategy_url: institution.strategyUrlEn },
  fr: { ...SHARED_PLACEHOLDERS, strategy_url: institution.strategyUrlFr },
};

const extract = (lang: Lang) => {
  const messages: Record<string, string> = {};

  for (const path in modules) {
    // Skip index.ts itself
    if (path.includes('index.ts')) continue;

    const mod = modules[path];

    const content = mod.default || mod;

    Object.keys(content).forEach((key) => {
      const message = content[key]?.[lang];
      if (message == null) return;
      // A few messages are vue-i18n message functions (common.ts); they
      // build their own text and hold no placeholders.
      messages[key] =
        typeof message === 'string'
          ? fillPlaceholders(message, PLACEHOLDERS[lang], key)
          : message;
    });
  }
  return messages;
};

export default {
  'en-US': extract('en'),
  'fr-CH': extract('fr'),
};
