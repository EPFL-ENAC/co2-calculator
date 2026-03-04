import { computed } from 'vue';
import { useColorblindStore } from 'src/stores/colorblind';
import { storeToRefs } from 'pinia';

// Get the store instance and export colorblindMode for backward compatibility
const colorblindStore = useColorblindStore();
const { enabled: colorblindMode } = storeToRefs(colorblindStore);
export { colorblindMode };

// Color definitions with default and colorblind variants
const colorDefinitions = {
  yellow: {
    default: {
      darker: '#FFF381',
      dark: '#FFFA9C',
      default: '#FFFEBA',
      light: '#FFFFD4',
      lighter: '#FFFFE8',
    },
    colorblind: {
      darker: '#D4A017',
      dark: '#E5B84F',
      default: '#F5D882',
      light: '#FAE8B0',
      lighter: '#FDF5D9',
    },
  },
  // 2
  peach: {
    default: {
      darker: '#FDD279',
      dark: '#FFDF96',
      default: '#FFEBB5',
      light: '#FFF4D4',
      lighter: '#FFFBE8',
    },
    colorblind: {
      darker: '#D97B2E',
      dark: '#E89B5C',
      default: '#F5B97E',
      light: '#F9D4AB',
      lighter: '#FCE9D3',
    },
  },
  // 3
  apricot: {
    default: {
      darker: '#FABF75',
      dark: '#FFD093',
      default: '#FFE0B3',
      light: '#FFE8C4',
      lighter: '#FFF0D5',
    },
    colorblind: {
      darker: '#C97A3E',
      dark: '#DC9B66',
      default: '#EDB88E',
      light: '#F4D3B5',
      lighter: '#FAE9D9',
    },
  },
  // 4
  lavender: {
    default: {
      darker: '#A69CCC',
      dark: '#BBB3DB',
      default: '#D1CBE8',
      light: '#E6D9F4',
      lighter: '#F2E6F2',
    },
    colorblind: {
      darker: '#5B7FC7',
      dark: '#7A9DD6',
      default: '#9ABBE5',
      light: '#BDD5F0',
      lighter: '#DDE9F8',
    },
  },
  // 4.5
  mauve: {
    default: {
      darker: '#BBA3CE',
      dark: '#C8B5D8',
      default: '#D5C7E2',
      light: '#E2D9EC',
      lighter: '#EDE8F2',
    },
    colorblind: {
      darker: '#7091CC',
      dark: '#8FADD9',
      default: '#ADC7E6',
      light: '#CBDDF2',
      lighter: '#E5EEF9',
    },
  },
  // 5
  lilac: {
    default: {
      darker: '#D0A9CF',
      dark: '#DDBDDC',
      default: '#E9D2E9',
      light: '#F0DCF0',
      lighter: '#F5E6F5',
    },
    colorblind: {
      darker: '#8AA3D1',
      dark: '#A5BBDE',
      default: '#C0D3EB',
      light: '#D9E5F4',
      lighter: '#EDF3FA',
    },
  },
  // 6
  periwinkle: {
    default: {
      darker: '#A5ADD8',
      dark: '#BAC0E4',
      default: '#CFD4EE',
      light: '#D9DEE9',
      lighter: '#E3E8F4',
    },
    colorblind: {
      darker: '#4A7BB8',
      dark: '#6996CC',
      default: '#8AB2E0',
      light: '#AFCFED',
      lighter: '#D4E6F6',
    },
  },
  // 7
  skyBlue: {
    default: {
      darker: '#A4BCE3',
      dark: '#B8CCEC',
      default: '#CEDDF4',
      light: '#D9E8F8',
      lighter: '#E5F2FC',
    },
    colorblind: {
      darker: '#3D8FC9',
      dark: '#5FA8D9',
      default: '#82C2E8',
      light: '#ACDAF2',
      lighter: '#D4EDF9',
    },
  },
  // 8
  babyBlue: {
    default: {
      darker: '#A2CBED',
      dark: '#B6D8F4',
      default: '#CDE5FA',
      light: '#D9E8F8',
      lighter: '#E5F2FC',
    },
    colorblind: {
      darker: '#2BA3D4',
      dark: '#52BCE3',
      default: '#7AD3F0',
      light: '#A8E4F6',
      lighter: '#D1F2FB',
    },
  },
  // 9
  aqua: {
    default: {
      darker: '#A1D9F7',
      dark: '#B5E4FC',
      default: '#CDE5FA',
      light: '#D9EDFC',
      lighter: '#E5F5FE',
    },
    colorblind: {
      darker: '#00A3B8',
      dark: '#2DBDD0',
      default: '#5DD6E6',
      light: '#91E6F0',
      lighter: '#C5F3F8',
    },
  },
  // 10
  mint: {
    default: {
      darker: '#A4D6D5',
      dark: '#B9E2E1',
      default: '#CFEDEC',
      light: '#D9F2F1',
      lighter: '#E6F7F6',
    },
    colorblind: {
      darker: '#00A896',
      dark: '#2DC2B3',
      default: '#5DD9CF',
      light: '#91E9E0',
      lighter: '#C5F4F0',
    },
  },
  // 11
  lightGreen: {
    default: {
      darker: '#A8D3AE',
      dark: '#BCE0C1',
      default: '#D1EBD5',
      light: '#E6F5EA',
      lighter: '#F2FBF2',
    },
    colorblind: {
      darker: '#3D9970',
      dark: '#5FB591',
      default: '#82D1B2',
      light: '#ACE3D0',
      lighter: '#D4F1E8',
    },
  },
  // 12
  paleYellowGreen: {
    default: {
      darker: '#ABCF84',
      dark: '#C0DEA0',
      default: '#D5EBBE',
      light: '#E5F2D4',
      lighter: '#F0F8EA',
    },
    colorblind: {
      darker: '#7AA832',
      dark: '#9AC156',
      default: '#B9D97E',
      light: '#D1E8A8',
      lighter: '#E8F4D1',
    },
  },
  // 13
  lightLavender: {
    default: {
      darker: '#C0A9D8',
      dark: '#D3BDE4',
      default: '#E6D1EE',
      light: '#F0D9F4',
      lighter: '#F5E6F5',
    },
    colorblind: {
      darker: '#6B8ACC',
      dark: '#8AA5DB',
      default: '#AAC0EA',
      light: '#CCDCF3',
      lighter: '#E6EEF9',
    },
  },
  notDefined: {
    default: {
      darker: '#000000',
      dark: '#000000',
      default: '#000000',
      light: '#000000',
      lighter: '#000000',
    },
    colorblind: {
      darker: '#000000',
      dark: '#000000',
      default: '#000000',
      light: '#000000',
      lighter: '#000000',
    },
  },
};

// Single computed that returns colors based on colorblind mode
export const colors = computed(() => {
  const mode = colorblindMode.value ? 'colorblind' : 'default';
  return {
    yellow: colorDefinitions.yellow[mode],
    peach: colorDefinitions.peach[mode],
    apricot: colorDefinitions.apricot[mode],
    lavender: colorDefinitions.lavender[mode],
    mauve: colorDefinitions.mauve[mode],
    lilac: colorDefinitions.lilac[mode],
    periwinkle: colorDefinitions.periwinkle[mode],
    skyBlue: colorDefinitions.skyBlue[mode],
    babyBlue: colorDefinitions.babyBlue[mode],
    aqua: colorDefinitions.aqua[mode],
    mint: colorDefinitions.mint[mode],
    lightGreen: colorDefinitions.lightGreen[mode],
    paleYellowGreen: colorDefinitions.paleYellowGreen[mode],
    lightLavender: colorDefinitions.lightLavender[mode],
    notDefined: colorDefinitions.notDefined[mode],
  };
});

// Helper function to add 0.5 opacity to hex color for uncertainty visualization using hex8 format
export const uncertaintyColor = (hex: string): string => {
  const alphaHex = '80';

  if (!hex) {
    return hex;
  }
  const cleanHex = hex.replace('#', '');
  if (cleanHex.length === 6) {
    return `#${cleanHex}${alphaHex}`;
  }

  if (cleanHex.length === 8) {
    const rgb = cleanHex.slice(0, 6);
    return `#${rgb}${alphaHex}`;
  }
  return hex;
};
