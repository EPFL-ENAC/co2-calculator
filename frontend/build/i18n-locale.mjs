// One chunk of texts per language.
//
// Why this exists: the files in src/i18n hold { en, fr } pairs, so a plain
// import ships both languages to every visitor. A module imported as
// `src/i18n/<file>.ts?lang=en` keeps only the English value of each pair,
// and the text files stay as the translators edit them.

const I18N_MODULE = /\/src\/i18n\/[^/]+\.ts\?lang=(en|fr)$/;

const propertyName = (property) =>
  property.type === 'Property' && !property.computed && property.key.name;

/** The value node of one language in a { en, fr } pair. Other shapes throw. */
const languageValue = (entry, lang, id) => {
  const pair = entry.type === 'Property' ? entry.value : entry;
  const names =
    pair.type === 'ObjectExpression' ? pair.properties.map(propertyName) : [];
  if (names.length !== 2 || !names.includes('en') || !names.includes('fr')) {
    throw new Error(
      `${id}: the text at offset ${entry.start} is not an { en, fr } pair`,
    );
  }
  return pair.properties[names.indexOf(lang)].value;
};

/** Keep one language of each pair in the default export of a text module. */
export const keepLanguage = (code, ast, lang, id) => {
  const texts = ast.body.find(
    (node) => node.type === 'ExportDefaultDeclaration',
  )?.declaration;
  if (texts?.type !== 'ObjectExpression') {
    throw new Error(`${id}: the default export must be an object of texts`);
  }
  let output = '';
  let cursor = 0;
  for (const entry of texts.properties) {
    const value = languageValue(entry, lang, id);
    output +=
      code.slice(cursor, entry.value.start) +
      code.slice(value.start, value.end);
    cursor = entry.value.end;
  }
  return output + code.slice(cursor);
};

export const i18nLocalePlugin = () => ({
  name: 'i18n-locale',
  // After the TypeScript transform: the parser reads JavaScript only.
  enforce: 'post',
  transform(code, id) {
    const lang = id.match(I18N_MODULE)?.[1];
    if (!lang) return null;
    return { code: keepLanguage(code, this.parse(code), lang, id), map: null };
  },
});
