import { ModuleConfig, ModuleField } from '@/constant/moduleConfig';
import { MODULES, MODULES_THRESHOLD_TYPES } from '@/constant/modules';
import { formatFTE } from '@/utils/number';
import type { Module } from '@/constant/modules';
import { SIUS_CODES } from '@/types/module-lookups.gen';

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
    required: true,
    sortable: true,
    ratio: '1/4',
    icon: 'o_filter_drama',
    columnSize: 'sm',
    editableInline: true,
  },
  {
    id: 'sius_code',
    labelKey: 'headcount-member-form-field-function-label',
    type: 'select',
    required: true,
    sortable: true,
    ratio: '1/4',
    icon: 'o_assignment_ind',
    optionLabelsAreKeys: true,
    columnSize: 'sm',
    editableInline: true,
    // #2254: imported rows may carry the "Other staff" sentinel (-1),
    // which is display-only — not offered in the dropdown options below.
    // renderCell falls back to this key template when no option matches.
    optionLabelKey: '{value}',

    options: SIUS_CODES.map((value) => ({ value, label: value })),
  },
  {
    id: 'user_institutional_id',
    labelKey: 'headcount-member-form-field-user-institutional-id-label',
    type: 'text',
    required: true,
    sortable: false,
    ratio: '1/4',
    editableInline: true,
  },
  {
    id: 'fte',
    labelKey: 'headcount-member-form-field-fte-label',
    type: 'number',
    required: true,
    min: 0,
    max: 1,
    step: 0.1,
    maxDecimals: 1,
    sortable: false,
    ratio: '1/4',
    icon: 'o_timer',
    editableInline: true,
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
    maxDecimals: 1,
    sortable: true,
    ratio: '12/12',
    icon: iconMap['o_timer'],
    tooltip: 'module-headcount-submodule-student-table-fte',
    editableInline: true,
  },
];

export const headcount: ModuleConfig = {
  id: 'module_headcount_001',
  type: MODULES.Headcount as Module,
  hasDescription: true,
  hasDescriptionSubtext: true,
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
      hasFormSubtitle: true,
      hasFormAddWithNote: false,
      hasTablePagination: false,
      hasTableAction: false,
      addButtonLabelKey: 'common_update_button',
      moduleFields: studentFields,
    },
  ],
};
