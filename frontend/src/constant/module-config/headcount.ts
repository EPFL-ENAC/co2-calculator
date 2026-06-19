import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';
import { MODULES, MODULES_THRESHOLD_TYPES } from 'src/constant/modules';
import { formatFTE } from 'src/utils/number';
import type { Module } from 'src/constant/modules';

import {
  outlinedFilterDrama,
  outlinedAssignmentInd,
  outlinedTimer,
} from '@quasar/extras/material-icons-outlined';

// EN : Name | Function | Full-Time Equivalent (FTE)
// FR : Nom | Fonction | Équivalent plein-temps (EPT)
const memberFields: ModuleField[] = [
  {
    id: 'name',
    labelKey: 'headcount-member-form-field-name-label',
    type: 'text',
    sortable: true,
    ratio: '1/4',
    icon: outlinedFilterDrama,
    columnSize: 'sm',
  },
  {
    id: 'sius_code',
    labelKey: 'headcount-member-form-field-function-label',
    type: 'select',
    sortable: true,
    ratio: '1/4',
    icon: outlinedAssignmentInd,
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
    ratio: '1/4',
  },
  {
    id: 'fte',
    labelKey: 'headcount-member-form-field-fte-label',
    type: 'number',
    min: 0,
    max: 1,
    step: 0.1,
    sortable: false,
    ratio: '1/4',
    icon: outlinedTimer,
  },
];

const studentFields: ModuleField[] = [
  {
    id: 'fte',
    labelKey: 'headcount-student_form_field_fte_label',
    type: 'number',
    min: 0,
    step: 0.1,
    sortable: true,
    ratio: '12/12',
    icon: outlinedTimer,
    tooltip: 'module-headcount-submodule-student-table-fte',
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
      moduleFields: memberFields,
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
