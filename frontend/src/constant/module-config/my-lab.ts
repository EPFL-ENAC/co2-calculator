import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';

// Define an icon map to convert string keys to SVG icons
import {
  outlinedFilterDrama,
  outlinedAssignmentInd,
  outlinedTimer,
} from '@quasar/extras/material-icons-outlined';
import { MODULES_THRESHOLD_TYPES } from 'src/constant/modules';

export const iconMap: Record<string, string> = {
  o_filter_drama: outlinedFilterDrama,
  o_assignment_ind: outlinedAssignmentInd,
  o_timer: outlinedTimer,
  // Add more mappings as needed
};

// EN : Name | Position | Full-Time Equivalent (FTE)
// FR : Nom | Position | Équivalent plein-temps (EPT)
const memberFields: ModuleField[] = [
  {
    id: 'display_name',
    labelKey: 'my-lab-member-form-field-name-label',
    type: 'text',
    sortable: true,
    required: true,
    ratio: '4/12',
    icon: 'o_filter_drama',
  },
  {
    id: 'function',
    labelKey: 'my-lab-member-form-field-position-label',
    type: 'text',
    sortable: true,
    ratio: '4/12',
    editableInline: true,
    icon: 'o_assignment_ind',
  },
  {
    id: 'fte',
    labelKey: 'my-lab-member-form-field-fte-label',
    type: 'number',
    required: true,
    min: 0,
    max: 1,
    step: 0.1,
    editableInline: true,
    ratio: '4/12',
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
    labelKey: 'my-lab-student_form_field_fte_label',
    type: 'number',
    required: true,
    min: 0,
    hideIn: { table: false },
  },
];

export const myLab: ModuleConfig = {
  id: 'module_water_001',
  type: 'my-lab',
  hasDescription: true,
  hasDescriptionSubtext: true,
  hasTooltip: true,
  name: 'Headcount',
  description:
    'Enter and verify team members and Full Time Equivalent (FTE) values for your unit',
  hasSubmodules: true,
  formStructure: 'perSubmodule',
  threshold: {
    type: MODULES_THRESHOLD_TYPES[0],
    value: 1000000, // FTE; implicit coloring only
  },
  submodules: [
    {
      id: 'member',
      type: 'member',
      tableNameKey: 'my-lab-member-table-title',
      moduleFields: memberFieldDynamicIcons,
    },
    {
      id: 'student',
      type: 'student',
      tableNameKey: 'my-lab-student-table-title',
      hasTableTopBar: false,
      hasFormSubtitle: true,
      hasStudentHelper: true,
      hasFormAddWithNote: false,
      addButtonLabelKey: 'common_update_button',
      moduleFields: studentFields,
    },
  ],
};
