export type FormStructure = 'single' | 'perSubmodule' | 'grouped';
export type FormInputType =
  | 'text'
  | 'number'
  | 'select'
  | 'date'
  | 'checkbox'
  | 'boolean';
export type ColumnType = 'text' | 'number' | 'select' | 'date';

export interface FormInput {
  id: string;
  label: string;
  type: FormInputType;
  icon?: string;
  required?: boolean;
  placeholder?: string;
  min?: number;
  max?: number;
  options?: Array<{ value: string; label: string }>;
  ratio?: string;
}

export interface TableColumn {
  key: string;
  label: string;
  type: ColumnType;
  unit?: string;
  sortable?: boolean;
  inputTypeName?: string;
  editableInline?: boolean;
  options?: Array<{ value: string; label: string }>;
  align?: 'left' | 'right' | 'center';
}

export interface Submodule {
  id: string;
  name: string;
  count?: number;
  tableColumns: TableColumn[];
  formInputs?: FormInput[];
}

export interface ModuleConfig {
  id: string;
  type: string;
  name: string;
  description: string;
  hasSubmodules: boolean;
  isCollapsible?: boolean;
  formStructure: FormStructure;
  formInputs?: FormInput[];
  submodules?: Submodule[];
  tableColumns?: TableColumn[];
}
