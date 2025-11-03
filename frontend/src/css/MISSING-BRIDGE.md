## Missing Variables

Here are the Quasar variables from full_quasar_variable_ref.scss that are **not** defined in \_quasar-bridge.scss:

cf: https://quasar.dev/style/sass-scss-variables#variables-list

### Core Variables

- `$animate-duration`, `$animate-delay`, `$animate-repeat`
- `$breakpoint-*` (all breakpoint variables)
- `$flex-cols`, `$flex-gutter-*` (all flex gutter variables)
- `$spaces`, `$flex-gutter`, `$sizes`, `$headings`, `$h-tags`, `$text-weights` (map variables)

### Typography

- All heading variables (`$h1` through `$h6`)
- `$subtitle1`, `$subtitle2`, `$body1`, `$body2`, `$overline`, `$caption`
- `$min-line-height`

### Color Palette

- All Material Design color variations (red, pink, purple, blue, etc. with their -1 through -14 variants)
- Named color variables like `$red`, `$pink`, `$blue`, etc.

### Z-index

- `$z-fab`, `$z-side`, `$z-marginals`, `$z-fixed-drawer`, `$z-fullscreen`, `$z-menu`, `$z-top`, `$z-tooltip`, `$z-notify`, `$z-max`

### Shadows

- `$shadow-*` (individual shadow levels 0-24)
- `$shadow-up-*` (upward shadow levels)
- `$shadows`, `$shadows-up` (shadow arrays)
- Dark mode shadows: `$dark-shadow-*`, `$dark-shadow-up-*`
- `$shadow-color`, `$shadow-transition`, `$inset-shadow`, `$inset-shadow-down`
- `$elevation-umbra`, `$elevation-penumbra`, `$elevation-ambient` (and dark variants)

### Component-specific

- `$ios-statusbar-height`
- `$avatar-*`, `$banner-*`, `$bar-*`, `$breadcrumbs-*`, `$carousel-*`, `$checkbox-*`, `$chip-*`, `$color-picker-*`, `$date-*`, `$field-*`, `$knob-*`, `$radio-*`, `$slide-*`, `$slider-*`, `$stepper-*`, `$tabs-*`, `$time-*`, `$timeline-*`, `$tree-*`, `$uploader-*`, `$option-*`, `$img-*`
- Layout: `$layout-shadow`, `$layout-shadow-dark`
- Menu: `$menu-box-shadow`, `$menu-box-shadow-dark`
- Table: `$table-box-shadow`, `$table-box-shadow-dark`, various table typography variables
- Rating: `$rating-shadow`

### Variables You Have Mapped

Your bridge file correctly maps these major categories:

- Brand colors (primary, secondary, accent, etc.)
- Base spacing system
- Basic typography (body font, line height)
- Button styling
- Basic borders and separators
- Input/form fields (partially)
- Cards (hover transition)
- Basic menu, tooltip, table variables
- Dialog, toolbar, rating (basic)
- Chat message styling

**Recommendation**: Your bridge file covers the most commonly used variables. The missing ones are mostly:

1. Component-specific sizing/typography that you might want to add as needed
2. The complete Material Design color palette (which you may not need if using your token system)
3. Shadow definitions (you're using your component tokens instead)
4. Advanced responsive/layout variables

This is a good starting point. Add missing variables only when you notice Quasar components not styling correctly.
