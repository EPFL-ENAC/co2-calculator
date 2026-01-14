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
  | 'radio-group'
  | 'direction-input';

export interface ConditionalVisibility {
  showWhen?: {
    fieldId: string;
    value: boolean | string | number | null;
  };
  hideWhen?: {
    fieldId: string;
    value: boolean | string | number | null;
  };
}

export interface ConditionalRatio {
  when: {
    fieldId: string;
    value: boolean | string | number | null;
  };
  ratio: string;
}

export interface ConditionalOptions {
  when: {
    fieldId: string;
    value: boolean | string | number | null;
  };
  showOptions: string[]; // Array of option values to show when condition is met
}

// Support multiple conditional options - first matching condition wins
export type ConditionalOptionsConfig =
  | ConditionalOptions
  | ConditionalOptions[];

export interface ModuleField {
  id: string;
  label?: string;
  labelKey?: string | string[];
  type: FieldType;
  required?: boolean;
  placeholder?: string;
  min?: number;
  max?: number;
  step?: number;
  default?: string | number | boolean;
  options?: Array<{ value: string; label: string }>;
  // Flat configuration (preferred): used by both table and form where relevant
  unit?: string;
  tooltip?: string;
  disable?: boolean;
  sortable?: boolean;
  inputTypeName?: string;
  editableInline?: boolean;
  readOnly?: boolean;
  align?: 'left' | 'right' | 'center';
  ratio?: string;
  icon?: string;
  maxColumnWidth?: number;
  hideIn?: {
    table?: boolean;
    form?: boolean;
  };
  // Conditional visibility based on another field's value
  conditionalVisibility?: ConditionalVisibility;
  // Dynamic ratio based on another field's value
  conditionalRatio?: ConditionalRatio;
  // Conditional options filtering based on another field's value
  // Can be a single condition or array of conditions (first match wins)
  conditionalOptions?: ConditionalOptionsConfig;
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
