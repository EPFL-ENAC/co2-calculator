// %placeholder% tokens in the texts, filled with institution values at
// startup (#3244, src/i18n/index.ts).

// A value is literal text, but vue-i18n reads these characters as message
// syntax ("@" starts a linked message): wrap each one in a literal.
const escapeForMessage = (value: string): string =>
  value.replace(/[@{}|$]/g, (char) => `{'${char}'}`);

/** Replace the %placeholder% tokens of one message. Unknown tokens throw. */
export const fillPlaceholders = (
  message: string,
  values: Record<string, string>,
  key: string,
): string =>
  message.replace(/%([a-z_]+)%/g, (_token, name: string) => {
    const value = values[name];
    if (value === undefined) {
      throw new Error(`i18n key "${key}" uses unknown placeholder %${name}%`);
    }
    return escapeForMessage(value);
  });
