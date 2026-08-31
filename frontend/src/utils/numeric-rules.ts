/**
 * Translate function shape expected from `useI18n()`'s `t` — kept minimal
 * so this stays a plain (non-Vue) utility and is trivial to unit test.
 */
type Translate = (key: string, params?: Record<string, unknown>) => string;

/**
 * Structural subset of ModuleTable's inline `TableViewColumn` type — that
 * type is declared inside the SFC and can't be imported, so this mirrors
 * `commitInline`'s own inline `col` param shape in the same file.
 */
type NumericRuleColumn = {
  min?: number;
  max?: number;
  maxDecimals?: number;
};

/**
 * Build the `q-input` validation rules for a numeric ModuleTable column
 * (number format, min, max, maxDecimals). Extracted from ModuleTable.vue's
 * `getNumericRules` so the min/max/maxDecimals narrowing can be unit-tested
 * without mounting the component.
 */
export function getNumericRules(col: NumericRuleColumn, t: Translate) {
  const rules = [];

  rules.push((val: string | number | null) => {
    if (val === '' || val === null || val === undefined) return true;
    const s = typeof val === 'string' ? val.trim() : String(val);
    if (s.includes(',')) return t('validation_use_dot_not_comma');
    return /^-?\d+(\.\d+)?$/.test(s) || t('validation_number_format');
  });

  if (col.min !== undefined) {
    const min = col.min;
    rules.push((val: string | number | null) => {
      const num = Number(val);
      return num >= min || t('validation_must_be_at_least', { min });
    });
  }

  if (col.max !== undefined) {
    const max = col.max;
    rules.push((val: string | number | null) => {
      const num = Number(val);
      return num <= max || t('validation_must_be_at_most', { max });
    });
  }

  if (col.maxDecimals !== undefined) {
    const maxDecimals = col.maxDecimals;
    rules.push((val: string | number | null) => {
      if (val === '' || val === null || val === undefined) return true;
      const s = typeof val === 'string' ? val.trim() : String(val);
      return (
        (s.split('.')[1]?.length ?? 0) <= maxDecimals ||
        // `count` doubles as the display value and the vue-i18n plural
        // index (see core-base's getPluralIndex): it reads named.count.
        t('validation_max_decimals', { count: maxDecimals })
      );
    });
  }

  return rules;
}
