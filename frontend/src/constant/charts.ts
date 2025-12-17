import { computed } from 'vue';
import { useColorblindStore } from 'src/stores/colorblind';
import { storeToRefs } from 'pinia';

// Get the store instance and export colorblindMode for backward compatibility
const colorblindStore = useColorblindStore();
const { enabled: colorblindMode } = storeToRefs(colorblindStore);
export { colorblindMode };

// Color definitions with default and colorblind variants
const colorDefinitions = {
  oliveGreen: {
    default: {
      darker: '#807F3A',
      dark: '#BFBA5C',
      default: '#FFF381',
      light: '#FFFA9C',
      lighter: '#FFFEBA',
    },
    colorblind: {
      darker: '#6B5B1A',
      dark: '#9B8B2D',
      default: '#D4C340',
      light: '#E6D966',
      lighter: '#F2E68C',
    },
  },
  brownOchre: {
    default: {
      darker: '#806B36',
      dark: '#BF9F56',
      default: '#FDD279',
      light: '#FFDF96',
      lighter: '#FFEBB5',
    },
    colorblind: {
      darker: '#6B4B1A',
      dark: '#9B6B2D',
      default: '#CC9440',
      light: '#E6B366',
      lighter: '#F2CC8C',
    },
  },
  orangeOchre: {
    default: {
      darker: '#806034',
      dark: '#BF9053',
      default: '#FABF75',
      light: '#FFD093',
      lighter: '#FFE0B3',
    },
    colorblind: {
      darker: '#8B3A1A',
      dark: '#B8552D',
      default: '#E67040',
      light: '#FF9466',
      lighter: '#FFB38C',
    },
  },
  purple: {
    default: {
      darker: '#524C68',
      dark: '#7B739B',
      default: '#A69CCC',
      light: '#BBB3DB',
      lighter: '#D1CBE8',
    },
    colorblind: {
      darker: '#3A4A6B',
      dark: '#556B9B',
      default: '#7094CC',
      light: '#94B3E6',
      lighter: '#B8CCF2',
    },
  },
  blueGrey: {
    default: {
      darker: '#4A5A7D',
      dark: '#5A6A8D',
      default: '#6A7A9D',
      light: '#7A8AAD',
      lighter: '#8A9ABD',
    },
    colorblind: {
      darker: '#2D4A6B',
      dark: '#40669B',
      default: '#5582CC',
      light: '#6B9BE6',
      lighter: '#8CB3F2',
    },
  },
  purpleGrey: {
    default: {
      darker: '#50556F',
      dark: '#7A80A4',
      default: '#A5ADD8',
      light: '#BAC0E4',
      lighter: '#CFD4EE',
    },
    colorblind: {
      darker: '#3A4A5B',
      dark: '#556B8B',
      default: '#7094BB',
      light: '#94B3D4',
      lighter: '#B8CCEB',
    },
  },
  blue: {
    default: {
      darker: '#4F5D75',
      dark: '#798CAD',
      default: '#A4BCE3',
      light: '#B8CCEC',
      lighter: '#CEDDF4',
    },
    colorblind: {
      darker: '#2D4A6B',
      dark: '#4066A3',
      default: '#5582D4',
      light: '#6B9BE6',
      lighter: '#8CB3F2',
    },
  },
  tealBlue: {
    default: {
      darker: '#2E7A8B',
      dark: '#3E8A9B',
      default: '#4E9AAB',
      light: '#5EAABB',
      lighter: '#6EBACB',
    },
    colorblind: {
      darker: '#1A5B6B',
      dark: '#2D7A9B',
      default: '#4099CC',
      light: '#66B3E6',
      lighter: '#8CCCF2',
    },
  },
  lightBlue: {
    default: {
      darker: '#4C6E80',
      dark: '#76A4BD',
      default: '#A1D9F7',
      light: '#B5E4FC',
      lighter: '#CCEDFF',
    },
    colorblind: {
      darker: '#2D5B6B',
      dark: '#407A9B',
      default: '#5599CC',
      light: '#6BB3E6',
      lighter: '#8CCCF2',
    },
  },
  forestGreen: {
    default: {
      darker: '#506E6D',
      dark: '#79A2A2',
      default: '#A4D6D5',
      light: '#B9E2E1',
      lighter: '#CFEDEC',
    },
    colorblind: {
      darker: '#3A5B5B',
      dark: '#557A8B',
      default: '#7099BB',
      light: '#94B3D4',
      lighter: '#B8CCEB',
    },
  },
  green: {
    default: {
      darker: '#526C56',
      dark: '#7CA081',
      default: '#A8D3AE',
      light: '#BCE0C1',
      lighter: '#D1EBD5',
    },
    colorblind: {
      darker: '#4A6B55',
      dark: '#669B70',
      default: '#85CC94',
      light: '#A3E6B3',
      lighter: '#C2F2CC',
    },
  },
  limeGreen: {
    default: {
      darker: '#566B3E',
      dark: '#809E60',
      default: '#ABCF84',
      light: '#C0DEA0',
      lighter: '#D5EBBE',
    },
    colorblind: {
      darker: '#5B6B3A',
      dark: '#7A9B55',
      default: '#99CC70',
      light: '#B3E694',
      lighter: '#CCF2B8',
    },
  },
  neutralGrey: {
    default: {
      darker: '#636576',
      dark: '#9699B0',
      default: '#C9CDE9',
      light: '#D5D9F0',
      lighter: '#E2E5F6',
    },
    colorblind: {
      darker: '#4A4A4A',
      dark: '#6B6B6B',
      default: '#999999',
      light: '#B8B8B8',
      lighter: '#D6D6D6',
    },
  },
  lightGrey: {
    default: {
      darker: '#6D6E79',
      dark: '#A4A5B5',
      default: '#DBDDF0',
      light: '#E3E5F5',
      lighter: '#ECEDF9',
    },
    colorblind: {
      darker: '#555555',
      dark: '#7A7A7A',
      default: '#A3A3A3',
      light: '#C2C2C2',
      lighter: '#E0E0E0',
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
    oliveGreen: colorDefinitions.oliveGreen[mode],
    brownOchre: colorDefinitions.brownOchre[mode],
    orangeOchre: colorDefinitions.orangeOchre[mode],
    purple: colorDefinitions.purple[mode],
    blueGrey: colorDefinitions.blueGrey[mode],
    purpleGrey: colorDefinitions.purpleGrey[mode],
    blue: colorDefinitions.blue[mode],
    tealBlue: colorDefinitions.tealBlue[mode],
    lightBlue: colorDefinitions.lightBlue[mode],
    forestGreen: colorDefinitions.forestGreen[mode],
    green: colorDefinitions.green[mode],
    limeGreen: colorDefinitions.limeGreen[mode],
    neutralGrey: colorDefinitions.neutralGrey[mode],
    lightGrey: colorDefinitions.lightGrey[mode],
    notDefined: colorDefinitions.notDefined[mode],
  };
});

// Helper function to add 0.5 opacity to hex color for uncertainty visualization using hex8 format
export const uncertaintyColor = (hex: string): string => {
  const alphaHex = '80';
  const cleanHex = hex.replace('#', '');
  return `#${cleanHex}${alphaHex}`;
};
