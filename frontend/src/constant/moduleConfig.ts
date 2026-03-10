import { Threshold } from 'src/constant/modules';
import type { AllSubmoduleTypes } from 'src/constant/modules';
export type FormStructure = 'single' | 'perSubmodule' | 'grouped';
export type FieldType =
  | 'text'
  | 'number'
  | 'select'
  | 'date'
  | 'checkbox'
  | 'boolean'
  | 'direction-input';

export interface ConditionalRatio {
  when: {
    fieldId: string;
    value: boolean | string | number | null;
  };
  ratio: string;
}

export interface ModuleField {
  id: string;
  label?: string;
  labelKey?: string | string[];
  type: FieldType;
  required?: boolean;
  placeholder?: string;
  hint?: string;
  min?: number;
  max?: number;
  step?: number;
  default?:
    | string
    | number
    | boolean
    | null
    | ((
        subModuleType: AllSubmoduleTypes,
        entry: Record<string, unknown>,
      ) => Promise<string | number | boolean | null>);
  path?: string[] | undefined;
  options?: Array<{ value: string; label: string }>;
  optionsId?: string; // ID to fetch options from store (kind or subkind)
  optionsFunction?: (
    subModuleType: AllSubmoduleTypes,
    entry: Record<string, unknown>,
  ) => Promise<Array<{ value: string; label: string }>>;
  appendFromFieldId?: string;
  // Flat configuration (preferred): used by both table and form where relevant
  unit?: string;
  tooltip?: string;
  disable?:
    | boolean
    | ((
        subModuleType: AllSubmoduleTypes,
        entry: Record<string, unknown>,
      ) => boolean);
  visible?: (
    subModuleType: AllSubmoduleTypes,
    entry: Record<string, unknown>,
  ) => boolean;
  sortable?: boolean;
  inputTypeName?: string;
  editableInline?: boolean;
  readOnly?: boolean;
  readOnlyWhenFilled?: boolean;
  align?: 'left' | 'right' | 'center';
  ratio?: string;
  icon?: string;
  maxColumnWidth?: number;
  hideIn?: {
    table?: boolean;
    form?: boolean;
  };
  // Dynamic ratio based on another field's value
  conditionalRatio?: ConditionalRatio;
  // When the specified row field has a value, this editable column renders as read-only text
  readOnlyWhen?: {
    fieldId: string; // check this field on the row
    hasValue: boolean; // true = read-only when field has a value
  };
  // When read-only due to readOnlyWhen, display this other field's value from the row
  readOnlyDisplayField?: string;
  // Whether to translate option labels through i18n
  optionLabelsAreKeys?: boolean;
}

export interface Submodule {
  id: string;
  type: AllSubmoduleTypes;
  name?: string; // deprecated, use nameKey instead
  nameKey?: string; // i18n key for submodule name
  tableNameKey?: string; // i18n key for table name
  count?: number;
  moduleFields: ModuleField[];
  hasTableTopBar?: boolean;
  hasFormSubtitle?: boolean;
  hasTablePagination?: boolean;
  hasStudentHelper?: boolean;
  hasFormTooltip?: boolean | string;
  hasFormAddWithNote?: boolean;
  hasTableAction?: boolean;
  addButtonLabelKey?: string;
  tooltipKey?: string;
  requiredFieldIds?: string[];
  csvTemplateHeaders?: string[];
}

export interface ResultBigNumberConfig {
  titleKey: string;
  numberKey: string;
  unit?: string;
  unitKey?: string;
  unitParams?: Record<string, string>;
  comparisonKey?: string;
  comparisonParams?: Record<string, string>;
  comparisonHighlight?: string;
  color?: 'positive' | 'negative' | 'primary' | 'secondary' | 'accent';
  tooltipKey?: string;
}

export interface ModuleConfig {
  id: string;
  type: string;
  name?: string;
  numberFormatOptions?: Intl.NumberFormatOptions;
  totalFormatter: (value: number | string | null | undefined) => string;
  description?: string;
  hasDescription: boolean;
  hasDescriptionSubtext?: boolean;
  hasTooltip: boolean;
  hasSubmodules: boolean;
  isCollapsible?: boolean;
  uncertainty?: 'high' | 'medium' | 'low';
  formStructure: FormStructure;
  moduleFields?: ModuleField[];
  submodules?: Submodule[];
  threshold?: Threshold;
  tableColumns?: ModuleField[];
  resultBigNumbers?: ResultBigNumberConfig[];
}
