import { boot } from 'quasar/wrappers';
import { createI18n } from 'vue-i18n';

import messages from 'src/i18n';

export type MessageLanguages = keyof typeof messages;
// Type-define 'en-US' as the master schema for the resource
export type MessageSchema = (typeof messages)['en-US'];

// See https://vue-i18n.intlify.dev/guide/advanced/typescript.html#global-resource-schema-type-definition

declare module 'vue-i18n' {
  // define the locale messages schema
  export interface DefineLocaleMessage extends MessageSchema {
    title: string;
  }

  // define the datetime format schema
  export interface DefineDateTimeFormat {
    short: Intl.DateTimeFormatOptions;
    long: Intl.DateTimeFormatOptions;
  }

  // define the number format schema
  export interface DefineNumberFormat {
    currency: Intl.NumberFormatOptions;
  }
}

export default boot(({ app }) => {
  const i18n = createI18n({
    locale: 'en-US',
    legacy: false,
    messages,
  });

  // Set i18n instance on app
  app.use(i18n);
});
