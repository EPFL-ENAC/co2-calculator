import type { TextModule } from '@/i18n';

// build/i18n-locale.mjs keeps the French value of each text (?lang=fr).
export default import.meta.glob<TextModule>(['../*.ts', '!../index.ts'], {
  eager: true,
  query: '?lang=fr',
  import: 'default',
});
