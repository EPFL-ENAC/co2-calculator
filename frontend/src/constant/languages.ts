export const LOCALE_MAP = { en: 'en-US', fr: 'fr-CH' } as const;
export const LANGUAGES = Object.keys(LOCALE_MAP) as Language[];

// Type-safe key for LOCALE_MAP
export type Locale = (typeof LOCALE_MAP)[Language];
export type Language = keyof typeof LOCALE_MAP;
