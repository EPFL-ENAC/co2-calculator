## Missing Quasar Variables

This document tracks Quasar variables from the official Quasar variable list that are **not** defined in `_quasar-bridge.scss`.

Reference: https://quasar.dev/style/sass-scss-variables#variables-list

**Last Updated**: After fixing font-weight values and regenerating token files

---

## ✅ Currently Mapped Variables

Your bridge file successfully maps these Quasar variables to our token system:

### Brand Colors

- ✅ `$primary`, `$secondary`, `$accent` → `dec.$color-primary`, `dec.$color-secondary`, `dec.$color-primary-hover`
- ✅ `$dark`, `$dark-page` → hardcoded `#1d1d1d`, `#121212`
- ✅ `$positive`, `$negative`, `$info`, `$warning` → `dec.$color-status-success/error/warning`

### Spacing System

- ✅ `$space-base`, `$space-x-base`, `$space-y-base` → `dec.$spacing-md` (0.75rem / 12px)
- ✅ `$space-none`, `$space-xs`, `$space-sm`, `$space-md`, `$space-lg`, `$space-xl` → Complete spacing map
  - xs: 0.25rem (4px)
  - sm: 0.5rem (8px)
  - md: 0.75rem (12px)
  - lg: 1rem (16px)
  - xl: 1.5rem (24px)

### Typography

- ✅ `$body-font-size` → `dec.$text-size-sm` (0.875rem / 14px)
- ✅ `$body-line-height` → `dec.$text-line-height-base` (1.25rem)
- ✅ `$typography-font-family` → 'Roboto', '-apple-system', sans-serif
- ✅ Font weights now correctly set: 400 (regular), 500 (medium), 700 (bold)

### Buttons

- ✅ `$button-border-radius` → `comp.$button-radius` (0.1875rem / 3px)
- ✅ `$button-rounded-border-radius` → `comp.$button-radius-rounded` (62.4375rem)
- ✅ `$button-push-border-radius` → `comp.$button-radius`
- ✅ `$button-padding` → `comp.$button-padding-y` `comp.$button-padding-x`
- ✅ `$button-dense-padding` → `comp.$button-padding-dense`
- ✅ `$button-font-size`, `$button-line-height`, `$button-font-weight` → mapped to components
- ✅ `$button-shadow`, `$button-shadow-active` → `none` (flat design)
- ✅ `$button-transition` → `0.3s ease`

### UI Elements

- ✅ `$separator-color` → `dec.$color-border` (#d5d5d5)
- ✅ `$separator-dark-color` → `rgba(255 255 255 / 28%)`
- ✅ `$generic-border-radius` → `dec.$radius-default-px` (3px)
- ✅ `$generic-hover-transition` → `0.3s cubic-bezier(0.25, 0.8, 0.5, 1)`
- ✅ `$dimmed-background`, `$light-dimmed-background` → rgba values

### Form Components

- ✅ **Input/Form fields**:
  - `$input-font-size` → `comp.$form-field-font-size` (0.875rem)
  - `$input-text-color` → `dec.$color-text` (#212121)
  - `$input-label-color` → `dec.$color-text-muted` (#8e8e8e)

### Layout Components

- ✅ **Menu**: `$menu-background`, `$menu-max-width` (95vw), `$menu-max-height` (65vh)
- ✅ **Tooltip**: Complete set (color, background, padding, border-radius, font sizes for desktop & mobile)
- ✅ **Table**: Border colors, hover/selected backgrounds (light & dark), border-radius, transition
- ✅ **Layout**: `$layout-border` → `1px solid $separator-color`
- ✅ **Badge**: `$badge-font-size` (0.75rem), `$badge-line-height` (1)
- ✅ **Item (lists)**: `$item-base-color` (#8e8e8e)
- ✅ **Editor**: All variables (borders, padding, hr colors, button gutter)
- ✅ **Chat**: All message variables (colors, backgrounds, border-radius, distances, padding)
- ✅ **Dialog**: `$dialog-title-font-size` (1.125rem), `$dialog-title-line-height` (1.6)
- ✅ **Toolbar**: Min height (50px), padding, title font size/weight
- ✅ **Rating**: `$rating-grade-color` (#ffc107)

---

## ⚠️ Missing Variables

### Core System Variables

#### Animation (3 variables)

```scss
$animate-duration: 0.3s !default;
$animate-delay: 0.3s !default;
$animate-repeat: 1 !default;
```

**Impact**: Low - Only affects Quasar's built-in animation utilities
**Recommendation**: Add if using `q-transition` or Quasar animations

#### Breakpoints (12+ variables)

```scss
$breakpoint-xs: 599px !default;
$breakpoint-sm: 1023px !default;
$breakpoint-md: 1439px !default;
$breakpoint-lg: 1919px !default;
// Plus: $breakpoint-xs-max, $breakpoint-sm-min/max, etc.
```

**Impact**: **HIGH** - Required for responsive utilities and Quasar grid system
**Recommendation**: **Add these ASAP** if using Quasar's responsive classes

#### Flex Grid System (6 variables)

```scss
$flex-cols: 12 !default;
$flex-gutter-xs: 4px !default;
$flex-gutter-sm: 8px !default;
$flex-gutter-md: 12px !default;
$flex-gutter-lg: 24px !default;
$flex-gutter-xl: 48px !default;
```

**Impact**: **HIGH** - Required for `q-gutter-*` classes
**Recommendation**: **Add if using Quasar grid/gutter utilities**

#### Map Variables (6 maps)

```scss
$spaces: (map of spacing values);
$flex-gutter: (map of gutter values);
$sizes: (map of breakpoint sizes);
$headings: (map of heading styles);
$h-tags: (map of h1-h6);
$text-weights: (map of font weights);
```

**Impact**: Medium - Used by Quasar's utility class generators
**Recommendation**: Add if using dynamic spacing/typography classes

---

### Typography System

#### Heading Variables (6 heading styles)

```scss
$h1: (
  size: 6rem,
  line-height: 6rem,
  letter-spacing: -0.01562em,
  weight: 300,
);
$h2: (
  size: 3.75rem,
  line-height: 3.75rem,
  letter-spacing: -0.00833em,
  weight: 300,
);
$h3: (
  size: 3rem,
  line-height: 3.125rem,
  letter-spacing: normal,
  weight: 400,
);
$h4: (
  size: 2.125rem,
  line-height: 2.5rem,
  letter-spacing: 0.00735em,
  weight: 400,
);
$h5: (
  size: 1.5rem,
  line-height: 2rem,
  letter-spacing: normal,
  weight: 400,
);
$h6: (
  size: 1.25rem,
  line-height: 2rem,
  letter-spacing: 0.0125em,
  weight: 500,
);
```

**Impact**: Medium - Only if using Quasar's `.text-h1` through `.text-h6` classes
**Recommendation**: Define your own heading system in components layer if needed

#### Text Styles (6 styles + 1 variable)

```scss
$subtitle1: (
  size: 1rem,
  line-height: 1.75rem,
  letter-spacing: 0.00937em,
  weight: 400,
);
$subtitle2: (
  size: 0.875rem,
  line-height: 1.375rem,
  letter-spacing: 0.00714em,
  weight: 500,
);
$body1: (
  size: 1rem,
  line-height: 1.5rem,
  letter-spacing: 0.03125em,
  weight: 400,
);
$body2: (
  size: 0.875rem,
  line-height: 1.25rem,
  letter-spacing: 0.01786em,
  weight: 400,
);
$overline: (
  size: 0.75rem,
  line-height: 2rem,
  letter-spacing: 0.16667em,
  weight: 500,
);
$caption: (
  size: 0.75rem,
  line-height: 1.25rem,
  letter-spacing: 0.03333em,
  weight: 400,
);
$min-line-height: 1.12;
```

**Impact**: Low - Only for Material Design typography classes
**Recommendation**: Skip unless using full Material typography system

---

### Material Design Color Palette

**280+ color variables** including:

- Base colors: `$red`, `$pink`, `$purple`, `$blue`, `$green`, `$yellow`, `$orange`, `$grey`, etc.
- Each with 14 variants: `$red-1` through `$red-14` (light to dark)
- Special variants: `$deep-purple`, `$light-blue`, `$blue-grey`, etc.

**Impact**: Low - Your custom color system is cleaner
**Recommendation**: **Skip entirely** - use your token-based colors instead

---

### Z-index Layers (10 variables)

```scss
$z-fab: 990 !default;
$z-side: 1000 !default;
$z-marginals: 2000 !default;
$z-fixed-drawer: 3000 !default;
$z-fullscreen: 6000 !default;
$z-menu: 6000 !default;
$z-top: 7000 !default;
$z-tooltip: 9000 !default;
$z-notify: 9500 !default;
$z-max: 9998 !default;
```

**Impact**: **HIGH** - Critical for proper layering of dialogs, drawers, tooltips, notifications
**Recommendation**: **Add these** - essential for proper component stacking

---

### Shadow System

#### Shadow Configuration (5 core variables)

```scss
$shadow-color: #000 !default;
$shadow-transition: box-shadow 0.28s cubic-bezier(0.4, 0, 0.2, 1) !default;
$inset-shadow: 0 7px 9px -7px rgba($shadow-color, 0.7) inset !default;
$inset-shadow-down: 0 -7px 9px -7px rgba($shadow-color, 0.7) inset !default;
$elevation-umbra: rgba($shadow-color, 0.2) !default;
$elevation-penumbra: rgba($shadow-color, 0.14) !default;
$elevation-ambient: rgba($shadow-color, 0.12) !default;
```

#### Elevation Levels (50 shadow variables)

- `$shadow-0` through `$shadow-24` (25 levels)
- `$shadow-up-0` through `$shadow-up-24` (25 upward shadows)

#### Dark Mode Shadows (54 additional variables)

- `$dark-shadow-color`, `$inset-dark-shadow`, elevation variants
- `$dark-shadow-0` through `$dark-shadow-24`
- `$dark-shadow-up-0` through `$dark-shadow-up-24`

#### Shadow Arrays (4 arrays)

```scss
$shadows: (array of 24 shadow levels);
$shadows-up: (array of 24 upward shadows);
$dark-shadows: (array of 24 dark shadows);
$dark-shadows-up: (array of 24 dark upward shadows);
```

**Impact**: Medium - Used by Quasar components for elevation (cards, dialogs, menus)
**Recommendation**: Add basic levels (0, 1, 2, 4, 8) if you want Material-style elevation

---

### Component-Specific Typography & Sizing

**100+ component-specific variables** for precise sizing control. Most have low impact unless you're heavily customizing specific components.

#### High Priority (add if using these components):

- `$field-*` variables (if using QField extensively)
- `$table-th-font-size`, `$table-tbody-td-font-size` (for custom table typography)
- `$tabs-icon-font-size` (if using icon tabs)

#### Medium Priority:

- `$avatar-font-size`, `$chip-font-size`, `$badge-min-height`
- `$stepper-*`, `$timeline-*` (if using these components)

#### Low Priority (add as needed):

- `$bar-*`, `$banner-*`, `$breadcrumbs-*`, `$carousel-*`
- `$checkbox-inner-font-size`, `$radio-inner-font-size`
- `$color-picker-*`, `$date-*`, `$time-*`
- `$knob-*`, `$slider-*`, `$uploader-*`, `$tree-*`
- `$img-*`, `$option-focus-transition`

#### Additional Component Variables:

- `$ios-statusbar-height: 20px` (for iOS mobile apps)
- `$layout-shadow`, `$layout-shadow-dark` (for layout elevation)
- `$menu-box-shadow`, `$menu-box-shadow-dark`
- `$table-box-shadow`, `$table-box-shadow-dark`
- `$rating-shadow`

---

## 📊 Coverage Summary

| Category                | Coverage | Variables Mapped | Priority   |
| ----------------------- | -------- | ---------------- | ---------- |
| ✅ Brand Colors         | 100%     | 9/9              | Critical   |
| ✅ Spacing System       | 100%     | 7/7              | Critical   |
| ✅ Basic Typography     | 100%     | 3/3              | Critical   |
| ✅ Buttons              | 100%     | 11/11            | High       |
| ✅ Core UI Elements     | 100%     | 7/7              | High       |
| ✅ Form Fields (basic)  | 100%     | 3/3              | High       |
| ✅ Common Components    | 100%     | 40+              | High       |
| ⚠️ Breakpoints          | 0%       | 0/12+            | **HIGH**   |
| ⚠️ Flex Grid System     | 0%       | 0/6              | **HIGH**   |
| ⚠️ Z-index Layers       | 0%       | 0/10             | **HIGH**   |
| ❌ Heading Styles       | 0%       | 0/6              | Medium     |
| ❌ Text Styles          | 0%       | 0/7              | Low        |
| ❌ Shadow System        | 0%       | 0/100+           | Medium     |
| ❌ Material Colors      | 0%       | 0/280+           | Low        |
| ❌ Component Typography | ~10%     | ~10/100+         | Low-Medium |
| ❌ Maps                 | 0%       | 0/6              | Medium     |

**Overall Coverage**: ~65% of commonly-used variables ✅

---

## 💡 Priority Recommendations

### 🔴 Critical - Add Immediately

1. **Breakpoints** - Required for responsive design
2. **Z-index layers** - Essential for proper component stacking
3. **Flex gutter variables** - Needed for grid utilities

### 🟡 Medium Priority - Add When Needed

1. **Basic shadow definitions** (levels 1, 2, 4, 8) - For elevation effects
2. **Map variables** - If using Quasar's utility class generators
3. **Heading typography** - Only if using `.text-h1`...`.text-h6` classes

### 🟢 Low Priority - Skip or Add Later

1. **Material Design color palette** - Your token system is cleaner
2. **All 24 shadow levels** - Excessive granularity
3. **Component-specific sizing** - Add only when specific components look wrong
4. **Text style maps** - Material Design specific

---

## ✅ System Health Check

### Font Weights

✅ **FIXED** - Now using correct numeric values:

```scss
$tokens-typography-font-weight-regular: 400 !default; // ✅ (was 25rem)
$tokens-typography-font-weight-medium: 500 !default; // ✅ (was 31.25rem)
$tokens-typography-font-weight-bold: 700 !default; // ✅ (was 43.75rem)
```

### Token System Architecture

✅ **Healthy** - Three-layer system working correctly:

- **Options** (62 primitives) → Raw design tokens
- **Decisions** (47 semantic tokens) → Meaningful names
- **Components** (80+ tokens) → Component-specific values
- **Quasar Bridge** (60+ mappings) → Framework integration

### Missing Critical Variables

⚠️ **Action Required**:

```scss
// Add to _quasar-bridge.scss:
$breakpoint-xs: 599px !default;
$breakpoint-sm: 1023px !default;
$breakpoint-md: 1439px !default;
$breakpoint-lg: 1919px !default;

$z-fab: 990 !default;
$z-side: 1000 !default;
$z-marginals: 2000 !default;
$z-fixed-drawer: 3000 !default;
$z-fullscreen: 6000 !default;
$z-menu: 6000 !default;
$z-top: 7000 !default;
$z-tooltip: 9000 !default;
$z-notify: 9500 !default;
$z-max: 9998 !default;

$flex-cols: 12 !default;
$flex-gutter-xs: dec.$spacing-xs !default;
$flex-gutter-sm: dec.$spacing-sm !default;
$flex-gutter-md: dec.$spacing-md !default;
$flex-gutter-lg: dec.$spacing-lg !default;
$flex-gutter-xl: dec.$spacing-xl !default;
```

---

## 🎯 Bottom Line

Your token system successfully provides 65% of Quasar's commonly-used variables. The missing critical variables (breakpoints, z-indexes, flex gutters) should be added to avoid runtime issues with responsive utilities and component layering. Everything else can be added incrementally as needed.

**Next Steps**:

1. ✅ Font weights fixed - No action needed
2. 🔴 Add breakpoints, z-indexes, and flex gutters to \_quasar-bridge.scss
3. 🟢 Monitor for component rendering issues
4. 🟢 Add additional variables only when specific problems arise

```

```

```

```
