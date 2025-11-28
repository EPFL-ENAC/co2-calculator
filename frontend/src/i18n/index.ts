type TranslationModule = {
  [key: string]: {
    en: string;
    fr: string;
  };
};

// Load all .ts files in the current directory eagerly
const modules = import.meta.glob<TranslationModule>('./*.ts', { eager: true });

type Lang = 'en' | 'fr';

const extract = (lang: Lang) => {
  const messages: Record<string, string> = {};

  for (const path in modules) {
    // Skip index.ts itself
    if (path.includes('index.ts')) continue;

    const mod = modules[path];
    // @ts-expect-error: The module structure is known but TS might complain about default export type
    const content = mod.default || mod;

    Object.keys(content).forEach((key) => {
      // @ts-expect-error
      if (content[key] && content[key][lang]) {
        // @ts-expect-error
        messages[key] = content[key][lang];
      }
    });
  }
  return messages;
};

export default {
  'en-US': extract('en'),
  'fr-CH': extract('fr'),
};
