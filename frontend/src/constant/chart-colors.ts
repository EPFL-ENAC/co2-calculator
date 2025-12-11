import { ref } from 'vue';

export interface ColorColumn {
  id: number;
  colors: string[];
  colorblindColors: string[];
}

export const colorblindMode = ref(false);

export const chartColorScale: ColorColumn[] = [
  // Column 1 - Olive Green/Brown tones
  {
    id: 1,
    colors: ['#807F3A', '#BFBA5C', '#FFF381', '#FFFA9C', '#FFFEBA'],
    colorblindColors: ['#6B5B1A', '#9B8B2D', '#D4C340', '#E6D966', '#F2E68C'],
  },

  // Column 2 - Brown/Ochre tones
  {
    id: 2,
    colors: ['#806B36', '#BF9F56', '#FDD279', '#FFDF96', '#FFEBB5'],
    colorblindColors: ['#6B4B1A', '#9B6B2D', '#CC9440', '#E6B366', '#F2CC8C'],
  },

  // Column 3 - Orange/Ochre tones
  {
    id: 3,
    colors: ['#806034', '#BF9053', '#FABF75', '#FFD093', '#FFE0B3'],
    colorblindColors: ['#8B3A1A', '#B8552D', '#E67040', '#FF9466', '#FFB38C'],
  },

  // Column 4 - Purple tones
  {
    id: 4,
    colors: ['#524C68', '#7B739B', '#A69CCC', '#BBB3DB', '#D1CBE8'],
    colorblindColors: ['#3A4A6B', '#556B9B', '#7094CC', '#94B3E6', '#B8CCF2'],
  },

  // Column 5 - Blue-Grey tones
  {
    id: 5,
    colors: ['#4A5A7D', '#5A6A8D', '#6A7A9D', '#7A8AAD', '#8A9ABD'],
    colorblindColors: ['#2D4A6B', '#40669B', '#5582CC', '#6B9BE6', '#8CB3F2'],
  },

  // Column 6 - Purple-Grey tones
  {
    id: 6,
    colors: ['#50556F', '#7A80A4', '#A5ADD8', '#BAC0E4', '#CFD4EE'],
    colorblindColors: ['#3A4A5B', '#556B8B', '#7094BB', '#94B3D4', '#B8CCEB'],
  },

  // Column 7 - Blue tones
  {
    id: 7,
    colors: ['#4F5D75', '#798CAD', '#A4BCE3', '#B8CCEC', '#CEDDF4'],
    colorblindColors: ['#2D4A6B', '#4066A3', '#5582D4', '#6B9BE6', '#8CB3F2'],
  },

  // Column 8 - Teal/Blue tones
  {
    id: 8,
    colors: ['#2E7A8B', '#3E8A9B', '#4E9AAB', '#5EAABB', '#6EBACB'],
    colorblindColors: ['#1A5B6B', '#2D7A9B', '#4099CC', '#66B3E6', '#8CCCF2'],
  },

  // Column 9 - Light Blue tones
  {
    id: 9,
    colors: ['#4C6E80', '#76A4BD', '#A1D9F7', '#B5E4FC', '#CCEDFF'],
    colorblindColors: ['#2D5B6B', '#407A9B', '#5599CC', '#6BB3E6', '#8CCCF2'],
  },

  // Column 10 - Forest Green tones
  {
    id: 10,
    colors: ['#506E6D', '#79A2A2', '#A4D6D5', '#B9E2E1', '#CFEDEC'],
    colorblindColors: ['#3A5B5B', '#557A8B', '#7099BB', '#94B3D4', '#B8CCEB'],
  },

  // Column 11 - Green tones
  {
    id: 11,
    colors: ['#526C56', '#7CA081', '#A8D3AE', '#BCE0C1', '#D1EBD5'],
    colorblindColors: ['#4A6B55', '#669B70', '#85CC94', '#A3E6B3', '#C2F2CC'],
  },

  // Column 12 - Lime Green tones
  {
    id: 12,
    colors: ['#566B3E', '#809E60', '#ABCF84', '#C0DEA0', '#D5EBBE'],
    colorblindColors: ['#5B6B3A', '#7A9B55', '#99CC70', '#B3E694', '#CCF2B8'],
  },

  // Column 13 - Purple-Grey tones
  {
    id: 13,
    colors: ['#5A5D72', '#888DAA', '#B7BDE0', '#C8CCE9', '#D9DDF2'],
    colorblindColors: ['#3A4A5B', '#55668B', '#7082BB', '#949ED4', '#B8BAEB'],
  },

  // Column 14 - Neutral Grey tones
  {
    id: 14,
    colors: ['#636576', '#9699B0', '#C9CDE9', '#D5D9F0', '#E2E5F6'],
    colorblindColors: ['#4A4A4A', '#6B6B6B', '#999999', '#B8B8B8', '#D6D6D6'],
  },

  // Column 15 - Light Grey tones
  {
    id: 15,
    colors: ['#6D6E79', '#A4A5B5', '#DBDDF0', '#E3E5F5', '#ECEDF9'],
    colorblindColors: ['#555555', '#7A7A7A', '#A3A3A3', '#C2C2C2', '#E0E0E0'],
  },

  // Column 16 - Not Defined
  {
    id: 16,
    colors: ['#000000', '#000000', '#000000', '#000000', '#000000'],
    colorblindColors: ['#000000', '#000000', '#000000', '#000000', '#000000'],
  },
];
export interface ChartElement {
  id: string;
  name: string;
  columnId: number;
}

export const chartElements: ChartElement[] = [
  { id: 'unit-gas', name: 'Unit Gas', columnId: 16 },
  { id: 'infrastructure-gas', name: 'Infrastructure Gas', columnId: 16 },
  { id: 'infrastructure-category', name: 'Infrastructure', columnId: 6 },
  { id: 'equipment', name: 'Equipment', columnId: 5 },
  { id: 'commuting', name: 'Commuting', columnId: 9 },
  { id: 'food', name: 'Food', columnId: 10 },
  {
    id: 'professional-travel-category',
    name: 'Professional Travel',
    columnId: 8,
  },
  { id: 'it', name: 'IT', columnId: 16 },
  {
    id: 'research-core-facilities',
    name: 'Research Core Facilities',
    columnId: 10,
  },
  { id: 'purchases', name: 'Purchases', columnId: 11 },
  { id: 'waste', name: 'Waste', columnId: 12 },
  { id: 'grey-energy', name: 'Grey Energy', columnId: 7 },
  {
    id: 'equipment-electric-consumption',
    name: 'Equipment',
    columnId: 5,
  },
  { id: 'internal-services', name: 'Internal Services', columnId: 2 },
  { id: 'external-cloud', name: 'External Cloud', columnId: 4 },
  { id: 'purchase', name: 'Purchase', columnId: 11 },
];

export const getElementColor = (
  elementId: string,
  shade: number = 2,
  colorblind?: boolean,
): string => {
  const columnId =
    chartElements.find((e) => e.id === elementId.toLowerCase())?.columnId ?? 14;
  const column =
    chartColorScale.find((c) => c.id === columnId) ?? chartColorScale[13];
  // Use provided colorblind parameter or fall back to reactive ref
  const useColorblind =
    colorblind !== undefined ? colorblind : colorblindMode.value;
  return (
    (useColorblind ? column.colorblindColors : column.colors)[shade] ??
    column.colors[2]
  );
};
