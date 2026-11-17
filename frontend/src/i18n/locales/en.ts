import type { TextModule } from '@/i18n';

// build/i18n-locale.mjs keeps the English value of each text (?lang=en).
export default import.meta.glob<TextModule>(['../*.ts', '!../index.ts'], {
  eager: true,
  query: '?lang=en',
  import: 'default',
});
