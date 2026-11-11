/**
 * Institution tokens in translation messages (#500).
 *
 * Messages in `src/i18n` name the institution with `%token%` placeholders
 * (for example `%institution%`). `src/i18n/index.ts` replaces them once, when
 * the messages load, with the values from `runtimeConfig.institution`. The
 * replacement runs before vue-i18n compiles the message, so no `t()` call
 * site passes the institution as a parameter.
 *
 * Pure module: no Vite, no DOM, so the unit tests can import it in Node.
 */

export type InstitutionTokenValues = Record<string, string>;

const TOKEN_PATTERN = /%([a-z_]+)%/g;

// Characters vue-i18n reads as message syntax. A configured value that holds
// one of them (the "@" of an email address) must reach the compiler as a
// literal interpolation such as {'@'}.
const MESSAGE_SYNTAX_PATTERN = /[@{}|]/g;

export function escapeForMessage(value: string): string {
  return value.replace(MESSAGE_SYNTAX_PATTERN, (char) => `{'${char}'}`);
}

export function replaceInstitutionTokens(
  message: string,
  values: InstitutionTokenValues,
): string {
  return message.replace(TOKEN_PATTERN, (_match, token: string) => {
    const value = values[token];
    // An unknown token is a typo in a translation file. Fail at load, or the
    // user reads a raw %token% in the page.
    if (value === undefined) {
      throw new Error(`Unknown institution token %${token}% in a translation`);
    }
    return escapeForMessage(value);
  });
}
