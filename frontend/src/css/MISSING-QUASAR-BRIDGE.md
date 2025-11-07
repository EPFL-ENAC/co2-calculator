## Missing Quasar Variables

This document tracks Quasar variables from the official Quasar variable list that are **not** defined in `_quasar-bridge.scss`.

Reference: https://quasar.dev/style/sass-scss-variables#variables-list

**Last Updated**: November 3, 2025 - Based on official Quasar v2 variables

---

## ✅ Currently Mapped Variables

Your bridge file successfully maps these Quasar variables to our token system:

### Brand Colors (9/9 = 100%)

- ✅ `$primary`, `$secondary`, `$accent` → `dec.$color-primary`, `dec.$color-secondary`, `dec.$color-primary-hover`
- ✅ `$dark`, `$dark-page` → hardcoded `#1d1d1d`, `#121212`
- ✅ `$positive`, `$negative`, `$info`, `$warning` → `dec.$color-status-*`

### Spacing System (13/16 = 81%)

- ✅ `$space-base`, `$space-x-base`, `$space-y-base` → `dec.$spacing-md` (0.75rem / 12px)
- ✅ `$space-none`, `$space-xs`, `$space-sm`, `$space-md`, `$space-lg`, `$space-xl` → Complete spacing map
  - xs: 0.25rem (4px)
  - sm: 0.5rem (8px)
  - md: 0.75rem (12px)
  - lg: 1rem (16px)
  - xl: 1.5rem (24px)
- ✅ `$flex-cols` → 12
- ✅ `$flex-gutter-xs/sm/md/lg/xl` → mapped to `dec.$spacing-*`
- ❌ **Missing**: `$spaces` (map), `$flex-gutter` (map), `$sizes` (map)

### Breakpoints (4/11 = 36%)

- ✅ `$breakpoint-xs` → 599px
- ✅ `$breakpoint-sm` → 1023px
- ✅ `$breakpoint-md` → 1439px
- ✅ `$breakpoint-lg` → 1919px
- ❌ **Missing**: `$breakpoint-xs-max`, `$breakpoint-sm-min`, `$breakpoint-sm-max`, `$breakpoint-md-min`, `$breakpoint-md-max`, `$breakpoint-lg-min`, `$breakpoint-lg-max`, `$breakpoint-xl-min`

### Z-index Layers (10/10 = 100%)

- ✅ All z-index variables: `$z-fab`, `$z-side`, `$z-marginals`, `$z-fixed-drawer`, `$z-fullscreen`, `$z-menu`, `$z-top`, `$z-tooltip`, `$z-notify`, `$z-max`

### Typography (4/20 = 20%)

- ✅ `$body-font-size` → `dec.$text-size-sm` (0.875rem / 14px)
- ✅ `$body-line-height` → `dec.$text-line-height-base` (1.25rem)
- ✅ `$typography-font-family` → 'Roboto', '-apple-system', sans-serif
- ✅ `$min-line-height` → NOT MAPPED (but exists in official variables at 1.12)
- ❌ **Missing**: `$h1` through `$h6` (6 heading maps)
- ❌ **Missing**: `$subtitle1`, `$subtitle2`, `$body1`, `$body2`, `$overline`, `$caption` (6 text style maps)
- ❌ **Missing**: `$headings` (map), `$h-tags` (map), `$text-weights` (map)

### Buttons (11/11 = 100%)

- ✅ All button variables mapped to components layer

### UI Core (10/10 = 100%)

- ✅ `$separator-color`, `$separator-dark-color`
- ✅ `$generic-border-radius`, `$generic-hover-transition`
- ✅ `$dimmed-background`, `$light-dimmed-background`
- ✅ `$input-font-size`, `$input-text-color`, `$input-label-color`
- ❌ **Missing**: `$input-autofill-color` (default: inherit)

### Layout Components

- ✅ **Menu** (3/5): background, max-width, max-height
  - ❌ Missing: `$menu-box-shadow`, `$menu-box-shadow-dark`
- ✅ **Tooltip** (9/9): Complete set
- ✅ **Table** (8/17): Basic colors and interactions
  - ❌ Missing: `$table-box-shadow`, `$table-box-shadow-dark`, `$table-th-font-size`, `$table-tbody-td-font-size`, `$table-title-font-size`, `$table-bottom-font-size`, `$table-nodata-icon-font-size`, `$table-sort-icon-font-size`, `$table-grid-item-*`, `$table-dense-sort-icon-font-size`
- ✅ **Layout** (1/3): border only
  - ❌ Missing: `$layout-shadow`, `$layout-shadow-dark`
- ✅ **Badge** (2/3): font-size, line-height
  - ❌ Missing: `$badge-min-height`
- ✅ **Item** (1/2): base-color
  - ❌ Missing: `$item-section-side-icon-font-size`, `$item-section-side-avatar-font-size`, `$item-label-header-*`
- ✅ **Editor** (8/8): Complete set
- ✅ **Chat** (5/9): Core colors and spacing
  - ❌ Missing: `$chat-message-name-font-size`, `$chat-message-stamp-font-size`, `$chat-message-label-font-size`, `$chat-message-avatar-size`
- ✅ **Dialog** (2/3): title font-size and line-height
  - ❌ Missing: `$dialog-title-letter-spacing`, `$dialog-progress-font-size`
- ✅ **Toolbar** (5/7): Most variables
  - ❌ Missing: `$toolbar-inset-size`, `$toolbar-title-letter-spacing`
- ✅ **Rating** (1/2): grade-color
  - ❌ Missing: `$rating-shadow`

---

## ⚠️ Missing Variables by Category

### 🔴 HIGH PRIORITY - Add These

#### 1. Animation Variables (3 variables) - **CRITICAL for transitions**

```scss
$animate-duration: 0.3s !default;
$animate-delay: 0.3s !default;
$animate-repeat: 1 !default;
```

**Impact**: Required for Quasar's `q-transition-*` components
**Recommendation**: **Add immediately** if using Quasar transitions

#### 2. Breakpoint Derivatives (7 variables) - **IMPORTANT for responsive utilities**

```scss
$breakpoint-xs-max: 599.98px !default;
$breakpoint-sm-min: 600px !default;
$breakpoint-sm-max: 1023.98px !default;
$breakpoint-md-min: 1024px !default;
$breakpoint-md-max: 1439.98px !default;
$breakpoint-lg-min: 1440px !default;
$breakpoint-lg-max: 1919.98px !default;
$breakpoint-xl-min: 1920px !default;
```

**Impact**: Used by Quasar's responsive classes and mixins
**Recommendation**: **Add if using advanced responsive utilities**

#### 3. Map Variables (3 critical maps)

```scss
$spaces: (
  'none': $space-none,
  'xs': $space-xs,
  'sm': $space-sm,
  'md': $space-md,
  'lg': $space-lg,
  'xl': $space-xl,
) !default;
$flex-gutter: (
  'none': 0,
  'xs': $flex-gutter-xs,
  'sm': $flex-gutter-sm,
  'md': $flex-gutter-md,
  'lg': $flex-gutter-lg,
  'xl': $flex-gutter-xl,
) !default;
$sizes: (
  'xs': 0,
  'sm': 600px,
  'md': 1024px,
  'lg': 1440px,
  'xl': 1920px,
) !default;
```

**Impact**: Required by Quasar's utility class generators
**Recommendation**: **Add if you see errors about missing maps**

---

### 🟡 MEDIUM PRIORITY - Add When Needed

#### 4. Typography System (16 variables)

```scss
// Heading maps
$h1: (
  size: 6rem,
  line-height: 6rem,
  letter-spacing: -0.01562em,
  weight: 300,
) !default;
$h2: (
  size: 3.75rem,
  line-height: 3.75rem,
  letter-spacing: -0.00833em,
  weight: 300,
) !default;
$h3: (
  size: 3rem,
  line-height: 3.125rem,
  letter-spacing: normal,
  weight: 400,
) !default;
$h4: (
  size: 2.125rem,
  line-height: 2.5rem,
  letter-spacing: 0.00735em,
  weight: 400,
) !default;
$h5: (
  size: 1.5rem,
  line-height: 2rem,
  letter-spacing: normal,
  weight: 400,
) !default;
$h6: (
  size: 1.25rem,
  line-height: 2rem,
  letter-spacing: 0.0125em,
  weight: 500,
) !default;

// Text style maps
$subtitle1: (
  size: 1rem,
  line-height: 1.75rem,
  letter-spacing: 0.00937em,
  weight: 400,
) !default;
$subtitle2: (
  size: 0.875rem,
  line-height: 1.375rem,
  letter-spacing: 0.00714em,
  weight: 500,
) !default;
$body1: (
  size: 1rem,
  line-height: 1.5rem,
  letter-spacing: 0.03125em,
  weight: 400,
) !default;
$body2: (
  size: 0.875rem,
  line-height: 1.25rem,
  letter-spacing: 0.01786em,
  weight: 400,
) !default;
$overline: (
  size: 0.75rem,
  line-height: 2rem,
  letter-spacing: 0.16667em,
  weight: 500,
) !default;
$caption: (
  size: 0.75rem,
  line-height: 1.25rem,
  letter-spacing: 0.03333em,
  weight: 400,
) !default;

// Typography maps
$headings: (map of all headings and text styles) !default;
$h-tags: (h1-h6 only) !default;
$text-weights: (
  thin: 100,
  light: 300,
  regular: 400,
  medium: 500,
  bold: 700,
  bolder: 900,
) !default;

// Additional
$min-line-height: 1.12 !default;
```

**Impact**: Only if using `.text-h1`, `.text-subtitle1`, etc. classes
**Recommendation**: Add if you adopt Material Design typography

#### 5. Shadow System (113 variables total)

```scss
// Core shadow config (5 variables)
$shadow-color: #000 !default;
$shadow-transition: box-shadow 0.28s cubic-bezier(0.4, 0, 0.2, 1) !default;
$inset-shadow: 0 7px 9px -7px rgba($shadow-color, 0.7) inset !default;
$inset-shadow-down: 0 -7px 9px -7px rgba($shadow-color, 0.7) inset !default;

// Elevation levels (3 variables)
$elevation-umbra: rgba($shadow-color, 0.2) !default;
$elevation-penumbra: rgba($shadow-color, 0.14) !default;
$elevation-ambient: rgba($shadow-color, 0.12) !default;

// 25 shadow levels: $shadow-0 through $shadow-24
// 25 upward shadows: $shadow-up-0 through $shadow-up-24
// 1 shadow array: $shadows
// 1 shadow-up array: $shadows-up

// Dark mode: Same structure (54 variables)
// $dark-shadow-color, $inset-dark-shadow, $inset-dark-shadow-down
// $elevation-dark-*, $dark-shadow-0 through $dark-shadow-24
// $dark-shadow-up-0 through $dark-shadow-up-24
// $dark-shadows, $dark-shadows-up
```

**Impact**: Used for elevation effects on cards, dialogs, menus, etc.
**Recommendation**: Add basic levels (1, 2, 4, 8) if you want Material elevation

#### 6. Component Shadows (3 variables)

```scss
$menu-box-shadow: $shadow-2 !default;
$menu-box-shadow-dark: $dark-shadow-2 !default;
$table-box-shadow: $shadow-2 !default;
$table-box-shadow-dark: $dark-shadow-2 !default;
$layout-shadow:
  0 0 10px 2px rgba($shadow-color, 0.2),
  0 0px 10px rgba($shadow-color, 0.24) !default;
$layout-shadow-dark:
  0 0 10px 2px rgba($dark-shadow-color, 0.2),
  0 0px 10px rgba($dark-shadow-color, 0.24) !default;
$rating-shadow:
  0 1px 3px rgba(0, 0, 0, 0.12),
  0 1px 2px rgba(0, 0, 0, 0.24) !default;
```

**Impact**: Adds depth to specific components
**Recommendation**: Add when components need elevation

---

### 🟢 LOW PRIORITY - Add Only If Specific Components Need Them

#### 7. Component-Specific Typography & Sizing (60+ variables)

**Avatar** (3 variables):

```scss
$avatar-font-size: 48px !default;
$avatar-content-font-size: 0.5em !default;
$avatar-content-line-height: 0.5em !default;
```

**Banner** (3 variables):

```scss
$banner-avatar-font-size: 46px !default;
$banner-avatar-icon-font-size: 40px !default;
$banner-avatar-dense-font-size: 28px !default;
```

**Bar/AppBar** (6 variables):

```scss
$bar-inner-font-size: 16px !default;
$bar-button-font-size: 11px !default;
$bar-dense-font-size: 14px !default;
$bar-dense-button-font-size: 8px !default;
$bar-height: 32px !default;
$bar-dense-height: 24px !default;
```

**Breadcrumbs** (1 variable):

```scss
$breadcrumbs-icon-font-size: 125% !default;
```

**Carousel** (1 variable):

```scss
$carousel-arrow-icon-font-size: 28px !default;
```

**Checkbox** (1 variable):

```scss
$checkbox-inner-font-size: 40px !default;
```

**Chip** (6 variables):

```scss
$chip-height: 2em !default;
$chip-font-size: 14px !default;
$chip-avatar-font-size: 2em !default;
$chip-dense-height: 1.5em !default;
$chip-dense-avatar-font-size: 1.5em !default;
```

**Color Picker** (1 variable):

```scss
$color-picker-tune-tab-input-font-size: 11px !default;
```

**Date Picker** (7 variables):

```scss
$date-header-subtitle-font-size: 14px !default;
$date-header-subtitle-line-height: 1.75 !default;
$date-header-subtitle-letter-spacing: 0.00938em !default;
$date-header-title-label-font-size: 24px !default;
$date-header-title-label-line-height: 1.2 !default;
$date-header-title-label-letter-spacing: 0.00735em !default;
$date-calendar-weekdays-inner-font-size: 12px !default;
```

**Field/Form** (13 variables):

```scss
$field-marginal-font-size: 24px !default;
$field-marginal-avatar-font-size: 32px !default;
$field-bottom-font-size: 12px !default;
$field-bottom-line-height: 1 !default;
$field-with-bottom-padding-bottom: 20px !default;
$field-label-font-size: 16px !default;
$field-label-line-height: 1.25 !default;
$field-label-top: 18px !default;
$field-label-letter-spacing: 0.00937em !default;
$field-dense-bottom-font-size: 11px !default;
$field-dense-with-bottom-padding-bottom: 19px !default;
$field-dense-label-font-size: 14px !default;
$field-dense-label-top: 10px !default;
$field-dense-marginal-avatar-font-size: 24px !default;
```

**Image** (6 variables):

```scss
$img-loading-font-size: 50px !default;
$img-content-position: absolute !default;
$img-content-padding: 16px !default;
$img-content-color: #fff !default;
$img-content-background: rgba(0, 0, 0, 0.47) !default;
```

**Knob** (1 variable):

```scss
$knob-font-size: 48px !default;
```

**Radio** (1 variable):

```scss
$radio-inner-font-size: 40px !default;
```

**Slider** (1 variable):

```scss
$slider-text-font-size: 12px !default;
```

**Slide Item** (2 variables):

```scss
$slide-item-active-text-font-size: 14px !default;
$slide-item-active-icon-font-size: 1.714em !default;
```

**Stepper** (7 variables):

```scss
$stepper-title-font-size: 14px !default;
$stepper-title-line-height: 1.285714 !default;
$stepper-title-letter-spacing: 0.1px !default;
$stepper-caption-font-size: 12px !default;
$stepper-caption-line-height: 1.16667 !default;
$stepper-dot-font-size: 14px !default;
$stepper-tab-font-size: 14px !default;
$stepper-dot-error-with-icon-font-size: 24px !default;
```

**Tabs** (5 variables):

```scss
$tabs-icon-font-size: 24px !default;
$tabs-icon-font-width: 24px !default;
$tabs-icon-font-height: 24px !default;
$tabs-alert-icon-font-size: 18px !default;
$tabs-arrow-font-size: 32px !default;
```

**Time Picker** (2 variables):

```scss
$time-header-label-font-size: 28px !default;
$time-clock-position-font-size: 12px !default;
```

**Timeline** (4 variables):

```scss
$timeline-subtitle-font-size: 12px !default;
$timeline-subtitle-letter-spacing: 1px !default;
$timeline-dot-icon-font-size: 16px !default;
$timeline-comfortable-heading-font-size: 200% !default;
```

**Tree** (1 variable):

```scss
$tree-icon-font-size: 21px !default;
```

**Uploader** (4 variables):

```scss
$uploader-title-font-size: 14px !default;
$uploader-title-line-height: 1.285714 !default;
$uploader-subtitle-font-size: 12px !default;
$uploader-subtitle-line-height: 1.5 !default;
```

**Other** (2 variables):

```scss
$option-focus-transition: 0.22s cubic-bezier(0, 0, 0.2, 1) !default;
$ios-statusbar-height: 20px !default;
```

---

### ⛔ SKIP ENTIRELY

#### Material Design Color Palette (280+ variables)

- `$red`, `$red-1` through `$red-14`
- `$pink`, `$pink-1` through `$pink-14`
- `$purple`, `$deep-purple`, `$indigo`, `$blue`, `$light-blue`
- `$cyan`, `$teal`, `$green`, `$light-green`, `$lime`
- `$yellow`, `$amber`, `$orange`, `$deep-orange`
- `$brown`, `$grey`, `$blue-grey`
- Each with 14 variants (1-14)

**Impact**: None - Your token system is cleaner and more maintainable
**Recommendation**: **Never add these** - use your custom color tokens instead

---

## 📊 Updated Coverage Summary

| Category                | Coverage | Variables Mapped | Priority   | Status |
| ----------------------- | -------- | ---------------- | ---------- | ------ |
| ✅ Brand Colors         | 100%     | 9/9              | Critical   | ✅     |
| ✅ Z-index Layers       | 100%     | 10/10            | Critical   | ✅     |
| ✅ Buttons              | 100%     | 11/11            | High       | ✅     |
| ✅ Editor               | 100%     | 8/8              | High       | ✅     |
| ✅ Tooltip              | 100%     | 9/9              | High       | ✅     |
| 🟡 Spacing System       | 81%      | 13/16            | Critical   | ⚠️     |
| 🟡 Breakpoints          | 36%      | 4/11             | High       | ⚠️     |
| 🟡 Table                | 47%      | 8/17             | High       | ⚠️     |
| 🟡 Typography (Basic)   | 20%      | 4/20             | Medium     | ⚠️     |
| 🟡 Menu                 | 60%      | 3/5              | Medium     | ⚠️     |
| 🟡 Layout               | 33%      | 1/3              | Medium     | ⚠️     |
| 🟡 Badge                | 67%      | 2/3              | Medium     | ⚠️     |
| 🟡 Chat                 | 56%      | 5/9              | Low-Medium | ⚠️     |
| 🟡 Dialog               | 67%      | 2/3              | Low-Medium | ⚠️     |
| 🟡 Toolbar              | 71%      | 5/7              | Low-Medium | ⚠️     |
| 🟡 Rating               | 50%      | 1/2              | Low        | ⚠️     |
| 🟡 Item                 | 25%      | 1/4              | Low        | ⚠️     |
| 🟡 Input                | 75%      | 3/4              | High       | ⚠️     |
| ❌ Animation            | 0%       | 0/3              | **HIGH**   | ⚠️     |
| ❌ Shadow System        | 0%       | 0/113            | Medium     | ❌     |
| ❌ Heading Styles       | 0%       | 0/6              | Medium     | ❌     |
| ❌ Text Styles          | 0%       | 0/7              | Low        | ❌     |
| ❌ Map Variables        | 0%       | 0/6              | High       | ⚠️     |
| ❌ Material Colors      | 0%       | 0/280+           | N/A (Skip) | ✅     |
| ❌ Component Typography | ~10%     | ~10/100+         | Low        | ❌     |
| ❌ Component Sizing     | ~5%      | ~5/60+           | Low        | ❌     |

**Overall Coverage**: ~70% of commonly-used variables ✅

---

## 💡 Action Items

### 🔴 IMMEDIATE - Add These Now

1. **Animation variables** (3 lines):

```scss
$animate-duration: 0.3s !default;
$animate-delay: 0.3s !default;
$animate-repeat: 1 !default;
```

2. **Required maps** (3 maps):

```scss
$spaces: (
  'none': $space-none,
  'xs': $space-xs,
  'sm': $space-sm,
  'md': $space-md,
  'lg': $space-lg,
  'xl': $space-xl,
) !default;
$flex-gutter: (
  'none': 0,
  'xs': $flex-gutter-xs,
  'sm': $flex-gutter-sm,
  'md': $flex-gutter-md,
  'lg': $flex-gutter-lg,
  'xl': $flex-gutter-xl,
) !default;
$sizes: (
  'xs': 0,
  'sm': 600px,
  'md': 1024px,
  'lg': 1440px,
  'xl': 1920px,
) !default;
```

### 🟡 WHEN NEEDED - Add If You See Errors

1. **Breakpoint derivatives** (if using responsive mixins)
2. **Basic shadow levels** (if components need elevation)
3. **Typography maps** (if using `.text-h*` classes)
4. **Component-specific variables** (only when that component looks wrong)

### 🟢 OPTIONAL - Add Later

1. Full shadow system (all 24 levels)
2. Component sizing variables
3. Advanced typography system

### ⛔ NEVER ADD

1. Material Design color palette (280+ variables)

---

## ✅ System Health

**Token Architecture**: ✅ Healthy

- Options (62 primitives)
- Decisions (47 semantic tokens)
- Components (80+ component tokens)
- Quasar Bridge (70+ mappings)

**Critical Systems**: ✅ All Essential Systems Working

- ✅ Colors & Branding
- ✅ Spacing & Layout
- ✅ Z-index Stacking
- ✅ Core Components (buttons, forms, tables)
- ⚠️ Missing animation config (add immediately)
- ⚠️ Missing map variables (add if errors occur)

**Risk Level**: 🟡 **LOW-MEDIUM**

- Most critical variables are covered
- Missing variables unlikely to cause issues unless specific features are used
- Add additional variables incrementally as needed

---

**Last Verification**: November 3, 2025
**Quasar Version**: v2.x
**Token System Version**: 1.0.0
