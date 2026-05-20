import {
  CHART_CATEGORY_COLOR_SCALES,
  MODULE_TO_CATEGORIES,
  colors,
} from 'src/constant/charts';

function lerpHex(a: string, b: string, t: number): string {
  const mix = (i: number) => {
    const av = parseInt(a.slice(i, i + 2), 16);
    const bv = parseInt(b.slice(i, i + 2), 16);
    return Math.round(av + (bv - av) * t)
      .toString(16)
      .padStart(2, '0');
  };
  return '#' + mix(1) + mix(3) + mix(5);
}

// Maps submodule type identifiers to their specific chart category.
// Only needed where a module has multiple submodules with different color scales.
const SUBMODULE_TO_CATEGORY: Record<string, string> = {
  building: 'buildings_room',
  energy_combustion: 'buildings_energy_combustion',
};

export interface ModuleIconColors {
  iconColor: string;
  // Raw values for use on arbitrary elements (cards, etc.)
  bgColor: string;
  bgColorLighter: string;
  borderColor: string;
  // Combined background shorthand using padding-box / border-box layering.
  // The element must have `border: 1.5px solid transparent` for the border layer to show.
  background: string;
  // Solid darker color or gradient using darker shades — for buttons.
  buttonBackground: string;
  // iconColor mixed toward black — readable on light backgrounds.
  buttonTextColor: string;
}

function asImage(v: string): string {
  return v.startsWith('linear-gradient') ? v : `linear-gradient(${v}, ${v})`;
}

export function makeBoxBackground(
  bgValue: string,
  borderValue: string,
): string {
  return `${asImage(bgValue)} padding-box, ${asImage(borderValue)} border-box`;
}

export function getModuleIconColors(
  moduleLink: string,
  submoduleType?: string,
): ModuleIconColors {
  const fallback = (): ModuleIconColors => ({
    iconColor: colors.value.yellow.darker,
    bgColor: colors.value.yellow.light,
    bgColorLighter: colors.value.yellow.lighter,
    borderColor: colors.value.yellow.dark,
    background: makeBoxBackground(
      colors.value.yellow.light,
      colors.value.yellow.dark,
    ),
    buttonBackground: colors.value.yellow.darker,
    buttonTextColor: lerpHex(colors.value.yellow.darker, '#000000', 0.5),
  });

  const categories = MODULE_TO_CATEGORIES.value[moduleLink];
  if (!categories?.length) return fallback();

  const overrideCategory =
    submoduleType && submoduleType in SUBMODULE_TO_CATEGORY
      ? SUBMODULE_TO_CATEGORY[submoduleType]
      : null;
  if (overrideCategory) {
    const scale =
      CHART_CATEGORY_COLOR_SCALES.value[
        overrideCategory as keyof typeof CHART_CATEGORY_COLOR_SCALES.value
      ];
    if (scale) {
      return {
        iconColor: scale.darker,
        bgColor: scale.light,
        bgColorLighter: scale.lighter,
        borderColor: scale.darker,
        background: makeBoxBackground(scale.light, scale.darker),
        buttonBackground: scale.darker,
        buttonTextColor: lerpHex(scale.darker, '#000000', 0.25),
      };
    }
  }

  const scales = categories
    .map(
      (cat) =>
        CHART_CATEGORY_COLOR_SCALES.value[
          cat as keyof typeof CHART_CATEGORY_COLOR_SCALES.value
        ],
    )
    .filter(Boolean);

  if (!scales.length) return fallback();

  if (scales.length > 1) {
    const stops = (shade: 'lighter' | 'light' | 'darker') =>
      scales
        .map(
          (s, i) =>
            `${s[shade]} ${Math.round((i * 100) / (scales.length - 1))}%`,
        )
        .join(', ');
    const bgGrad = `linear-gradient(to left, ${stops('light')})`;
    const bgLighterGrad = `linear-gradient(to left, ${stops('lighter')})`;
    const borderGrad = `linear-gradient(to left, ${stops('darker')})`;
    const btnGrad = `linear-gradient(to left, ${stops('darker')})`;
    return {
      iconColor: scales[0].darker,
      bgColor: bgGrad,
      bgColorLighter: bgLighterGrad,
      borderColor: scales[0].darker,
      background: makeBoxBackground(bgGrad, borderGrad),
      buttonBackground: btnGrad,
      buttonTextColor: lerpHex(scales[0].darker, '#000000', 0.25),
    };
  }

  return {
    iconColor: scales[0].darker,
    bgColor: scales[0].light,
    bgColorLighter: scales[0].lighter,
    borderColor: scales[0].darker,
    background: makeBoxBackground(scales[0].light, scales[0].darker),
    buttonBackground: scales[0].darker,
    buttonTextColor: lerpHex(scales[0].darker, '#000000', 0.25),
  };
}

function getSubmoduleScale(
  submoduleType: string | undefined,
  moduleLink: string,
) {
  if (submoduleType && submoduleType in SUBMODULE_TO_CATEGORY) {
    const category = SUBMODULE_TO_CATEGORY[submoduleType];
    const scale =
      CHART_CATEGORY_COLOR_SCALES.value[
        category as keyof typeof CHART_CATEGORY_COLOR_SCALES.value
      ];
    if (scale) return scale;
  }
  const categories = MODULE_TO_CATEGORIES.value[moduleLink];
  if (categories?.length) {
    const scale =
      CHART_CATEGORY_COLOR_SCALES.value[
        categories[0] as keyof typeof CHART_CATEGORY_COLOR_SCALES.value
      ];
    if (scale) return scale;
  }
  return colors.value.yellow;
}

export function getSubmoduleIconColor(
  submoduleType: string | undefined,
  moduleLink: string,
): string {
  return getSubmoduleScale(submoduleType, moduleLink).darker;
}

export function getSubmoduleLighterColor(
  submoduleType: string | undefined,
  moduleLink: string,
): string {
  return getSubmoduleScale(submoduleType, moduleLink).lighter;
}
