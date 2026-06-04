import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { MODULES, MODULES_THRESHOLD_TYPES } from 'src/constant/modules';
import { formatFTE } from 'src/utils/number';
import type { Module } from 'src/constant/modules';

// Define an icon map to convert string keys to SVG icons
import {
  outlinedFilterDrama,
  outlinedAssignmentInd,
  outlinedTimer,
} from '@quasar/extras/material-icons-outlined';

export const iconMap: Record<string, string> = {
  o_filter_drama: outlinedFilterDrama,
  o_assignment_ind: outlinedAssignmentInd,
  o_timer: outlinedTimer,
  // Add more mappings as needed
};

// EN : Name | Function | Full-Time Equivalent (FTE)
// FR : Nom | Fonction | Équivalent plein-temps (EPT)
const memberFields: ModuleField[] = [
  {
    id: 'name',
    labelKey: 'headcount-member-form-field-name-label',
    type: 'text',
    sortable: true,
    required: true,
    ratio: '1/4',
    icon: 'o_filter_drama',
    columnSize: 'sm',
  },
  {
    id: 'sius_code',
    labelKey: 'headcount-member-form-field-function-label',
    type: 'select',
    sortable: true,
    required: true,
    requiredMessageKey: 'headcount-member-function-required',
    editableInline: true,
    ratio: '1/4',
    icon: 'o_assignment_ind',
    optionLabelsAreKeys: true,
    columnSize: 'sm',
    options: [
      { value: '51', label: '51' },
      { value: '52', label: '52' },
      { value: '53', label: '53' },
      { value: '54', label: '54' },
      { value: '56', label: '56' },
      { value: '57', label: '57' },
      { value: '58', label: '58' },
      { value: '59', label: '59' },
    ],
  },
  {
    id: 'user_institutional_id',
    labelKey: 'headcount-member-form-field-user-institutional-id-label',
    type: 'text',
    sortable: false,
    required: true,
    ratio: '1/4',
  },
  {
    id: 'fte',
    labelKey: 'headcount-member-form-field-fte-label',
    type: 'number',
    required: true,
    min: 0,
    max: 1,
    step: 0.1,
    sortable: false,
    editableInline: true,
    ratio: '1/4',
    icon: 'o_timer',
  },
];

const memberFieldDynamicIcons = memberFields.map((field) => ({
  ...field,
  icon: iconMap[field.icon],
}));

const studentFields: ModuleField[] = [
  {
    id: 'fte',
    labelKey: 'headcount-student_form_field_fte_label',
    type: 'number',
    required: true,
    min: 0,
    step: 0.1,
    sortable: true,
    editableInline: true,
    ratio: '12/12',
    icon: iconMap['o_timer'],
  },
];

export const headcount: ModuleConfig = {
  id: 'module_headcount_001',
  type: MODULES.Headcount as Module,
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  hasTooltipSubText: true,
  name: 'Headcount',
  description:
    'Enter and verify team members and Full Time Equivalent (FTE) values for your unit',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  threshold: {
    type: MODULES_THRESHOLD_TYPES[0],
    value: 1000000, // FTE; implicit coloring only
  },
  numberFormatOptions: {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  },
  totalFormatter: formatFTE,
  submodules: [
    {
      id: 'member',
      type: 'member',
      tableNameKey: 'headcount-member-table-title',
      moduleFields: memberFieldDynamicIcons,
      hasFormTooltip: false,
      csvTemplateHeaders: [
        'name',
        'sius_code',
        'user_institutional_id',
        'fte',
        'note',
      ],
    },
    {
      id: 'student',
      type: 'student',
      tableNameKey: 'headcount-student-table-title',
      hasTableTopBar: false,
      hasFormTooltip: false,
      hasFormSubtitle: true,
      hasFormAddWithNote: false,
      hasTablePagination: false,
      hasTableAction: false,
      addButtonLabelKey: 'common_update_button',
      moduleFields: studentFields,
    },
  ],
};
