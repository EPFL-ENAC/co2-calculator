import { Threshold } from 'src/constant/modules';
import type { AllSubmoduleTypes } from 'src/constant/modules';
export type FormStructure = 'single' | 'perSubmodule' | 'grouped';
export type FieldType =
  | 'text'
  | 'number'
  | 'select'
  | 'date'
  | 'checkbox'
  | 'boolean';

export interface ModuleField {
  id: string;
  label?: string;
  labelKey?: string;
  type: FieldType;
  required?: boolean;
  placeholder?: string;
  min?: number;
  max?: number;
  options?: Array<{ value: string; label: string }>;
  // Flat configuration (preferred): used by both table and form where relevant
  unit?: string;
  tooltip?: string;
  sortable?: boolean;
  inputTypeName?: string;
  editableInline?: boolean;
  readOnly?: boolean;
  align?: 'left' | 'right' | 'center';
  ratio?: string;
  icon?: string;
  hideIn?: {
    table?: boolean;
    form?: boolean;
  };
}

export interface Submodule {
  id: string;
  type: AllSubmoduleTypes;
  name?: string; // deprecated, use nameKey instead
  nameKey?: string; // i18n key for submodule name
  tableNameKey?: string; // i18n key for table name
  count?: number;
  moduleFields: ModuleField[];
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
