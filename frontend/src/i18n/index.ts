import { runtimeConfig } from '@/config/runtime';
import { replaceInstitutionTokens } from '@/utils/institutionTokens';

type TranslationModule = {
  [key: string]: {
    en: string;
    fr: string;
  };
};

// Load all .ts files in the current directory eagerly
const modules = import.meta.glob<TranslationModule>('./*.ts', { eager: true });

type Lang = 'en' | 'fr';

// %token% placeholders the translation files can use (#500). The values come
// from the APP_INSTITUTION_* block of the runtime configuration.
const { institution } = runtimeConfig;
const institutionTokens = {
  institution: institution.name,
  institution_fr_de: institution.nameFrDe,
  institution_fr_a: institution.nameFrA,
  institution_id_label: institution.idLabel,
  contact_email: institution.contactEmail,
  strategy_url: institution.strategyUrl,
  strategy_url_fr: institution.strategyUrlFr,
  user_doc_url: institution.userDocUrl,
  backoffice_doc_url: institution.backofficeDocUrl,
};

const extract = (lang: Lang) => {
  const messages: Record<string, string> = {};

  for (const path in modules) {
    // Skip index.ts itself
    if (path.includes('index.ts')) continue;

    const mod = modules[path];

    const content = mod.default || mod;

    Object.keys(content).forEach((key) => {
      if (content[key] != null && content[key][lang] != null) {
        const message = content[key][lang];
        // common.ts also holds message functions (plural rules); they carry
        // no token and pass through unchanged.
        messages[key] =
          typeof message === 'string'
            ? replaceInstitutionTokens(message, institutionTokens)
            : message;
      }
    });
  }
  return messages;
};

export default {
  'en-US': extract('en'),
  'fr-CH': extract('fr'),
};
