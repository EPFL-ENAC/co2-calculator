export interface ColorColumn {
  id: number;
  colors: string[]; // 5 shades: [darkest, dark, base, light, lightest]
  colorblindColors: string[]; // 5 shades for colorblind users
}

export const chartColorScale: ColorColumn[] = [
  // Column 1 - Olive Green/Brown tones
  {
    id: 1,
    colors: ['#807F3A', '#BFBA5C', '#FFF381', '#FFFA9C', '#FFFEBA'],
    colorblindColors: ['#8B6914', '#B8941F', '#E6C02A', '#FFD93D', '#FFE666'],
  },

  // Column 2 - Brown/Ochre tones
  {
    id: 2,
    colors: ['#806B36', '#BF9F56', '#FDD279', '#FFDF96', '#FFEBB5'],
    colorblindColors: ['#B85C0A', '#E67E1A', '#FF9F2A', '#FFB84D', '#FFD170'],
  },

  // Column 3 - Orange/Ochre tones
  {
    id: 3,
    colors: ['#806034', '#BF9053', '#FABF75', '#FFD093', '#FFE0B3'],
    colorblindColors: ['#8B1A1A', '#B82D2D', '#E64040', '#FF6666', '#FF8C8C'],
  },

  // Column 4 - Purple tones
  {
    id: 4,
    colors: ['#524C68', '#7B739B', '#A69CCC', '#BBB3DB', '#D1CBE8'],
    colorblindColors: ['#8B1A5C', '#B82D7A', '#E64098', '#FF66B3', '#FF8CCC'],
  },

  // Column 5 - Blue-Grey tones
  {
    id: 5,
    colors: ['#4A5A7D', '#5A6A8D', '#6A7A9D', '#7A8AAD', '#8A9ABD'],
    colorblindColors: ['#5C1A8B', '#7A2DB8', '#9840E6', '#B366FF', '#CC8CFF'],
  },

  // Column 6 - Purple-Grey tones
  {
    id: 6,
    colors: ['#50556F', '#7A80A4', '#A5ADD8', '#BAC0E4', '#CFD4EE'],
    colorblindColors: ['#1A3A8B', '#2D4DB8', '#4060E6', '#6673FF', '#8C99FF'],
  },

  // Column 7 - Blue tones
  {
    id: 7,
    colors: ['#4F5D75', '#798CAD', '#A4BCE3', '#B8CCEC', '#CEDDF4'],
    colorblindColors: ['#1A5C8B', '#2D7AB8', '#4098E6', '#66B3FF', '#8CCCFF'],
  },

  // Column 8 - Teal/Blue tones
  {
    id: 8,
    colors: ['#2E7A8B', '#3E8A9B', '#4E9AAB', '#5EAABB', '#6EBACB'],
    colorblindColors: ['#1A8B7A', '#2DB8A3', '#40E6CC', '#66FFE0', '#8CFFE6'],
  },

  // Column 9 - Light Blue tones
  {
    id: 9,
    colors: ['#4C6E80', '#76A4BD', '#A1D9F7', '#B5E4FC', '#CCEDFF'],
    colorblindColors: ['#3A8B1A', '#4DB82D', '#60E640', '#73FF66', '#99FF8C'],
  },

  // Column 10 - Forest Green tones
  {
    id: 10,
    colors: ['#506E6D', '#79A2A2', '#A4D6D5', '#B9E2E1', '#CFEDEC'],
    colorblindColors: ['#5C8B1A', '#7AB82D', '#98E640', '#B3FF66', '#CCFF8C'],
  },

  // Column 11 - Green tones
  {
    id: 11,
    colors: ['#526C56', '#7CA081', '#A8D3AE', '#BCE0C1', '#D1EBD5'],
    colorblindColors: ['#7A8B1A', '#A3B82D', '#CCE640', '#E0FF66', '#E6FF8C'],
  },

  // Column 12 - Lime Green tones
  {
    id: 12,
    colors: ['#566B3E', '#809E60', '#ABCF84', '#C0DEA0', '#D5EBBE'],
    colorblindColors: ['#8B5C1A', '#B87A2D', '#E69840', '#FFB366', '#FFCC8C'],
  },

  // Column 13 - Purple-Grey tones
  {
    id: 13,
    colors: ['#5A5D72', '#888DAA', '#B7BDE0', '#C8CCE9', '#D9DDF2'],
    colorblindColors: ['#4A5A6B', '#6B7A8B', '#8C9AAB', '#ADBACB', '#CED5DB'],
  },

  // Column 14 - Neutral Grey tones
  {
    id: 14,
    colors: ['#636576', '#9699B0', '#C9CDE9', '#D5D9F0', '#E2E5F6'],
    colorblindColors: ['#4A4A4A', '#6B6B6B', '#8C8C8C', '#ADADAD', '#CECECE'],
  },

  // Column 15 - Light Grey tones
  {
    id: 15,
    colors: ['#6D6E79', '#A4A5B5', '#DBDDF0', '#E3E5F5', '#ECEDF9'],
    colorblindColors: ['#6B6B6B', '#8C8C8C', '#ADADAD', '#CECECE', '#EFEFEF'],
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
  { id: 'grey-energy', name: 'Grey Energy', columnId: 15 },
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
  colorblind: boolean = false,
): string => {
  const columnId =
    chartElements.find((e) => e.id === elementId.toLowerCase())?.columnId ?? 14;
  const column =
    chartColorScale.find((c) => c.id === columnId) ?? chartColorScale[13];
  return (
    (colorblind ? column.colorblindColors : column.colors)[shade] ??
    column.colors[2]
  );
};
