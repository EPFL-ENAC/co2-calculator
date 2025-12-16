import { ModuleConfig, ModuleField } from 'src/constant/moduleConfig';

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

// EN : Name | Position | Full-Time Equivalent (FTE)
// FR : Nom | Position | Équivalent plein-temps (EPT)
const memberFields: ModuleField[] = [
  {
    id: 'name',
    label: 'Name',
    type: 'text',
    sortable: true,
    required: true,
    ratio: '4/12',
    icon: 'o_filter_drama',
  },
  {
    id: 'position',
    label: 'Position',
    type: 'text',
    sortable: true,
    ratio: '4/12',
    icon: 'o_assignment_ind',
  },
  {
    id: 'fte',
    label: 'Full-Time Equivalent (FTE)',
    type: 'number',
    required: true,
    min: 0,
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
    id: 'position',
    label: 'Position',
    type: 'text',
    hideIn: { form: true },
    sortable: true,
  },
  {
    id: 'fte',
    label: 'Full-Time Equivalent (FTE)',
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
  submodules: [
    {
      id: 'member',
      type: 'member',
      name: 'Member',
      moduleFields: memberFieldDynamicIcons,
    },
    {
      id: 'student',
      type: 'student',
      name: 'Student',
      moduleFields: studentFields,
    },
  ],
};
