# Implementation Plan: Improve Module Validation UX (Issue #265)

## Overview

Improve the module validation user experience by making the validation process more intuitive and moving key elements closer to where users are working.

---

## Proposed Changes

### 1. Move Total Section to Top

- **Current position**: Below table, above bottom navigation
- **New position**: Between Module Title and Module Charts
- **Benefit**: Users see results prominently at page top, not hidden below data entry

### 2. Integrate Validation Button into Total Section

- **Current location**: Header (top-right corner)
- **New location**: Inside Total section card, on the right side
- **Benefit**: Validation action is next to the result it affects, creating clear cause-and-effect

### 3. Conditional Total Display

- **When NOT validated**: Show "work in progress, validate to see the results" message
- **When validated**: Show calculated total value
- **Benefit**: Clear visual feedback about module completion state

### 4. Remove Decimals from Total

- **Current**: Shows values like "1,234.56 t CO₂-eq"
- **New**: Shows whole numbers like "1,235 t CO₂-eq"
- **Benefit**: More appropriate for ton-scale emissions reporting

---

## Design Decisions

### Validation Button Position

✅ **Selected approach**: In Total section (top of page)

- Creates direct connection between validation action and result display
- Highly visible without being intrusive
- Follows principle of "controls near affected elements"

### Validation Enforcement

✅ **Selected approach**: No enforcement - allow validation with incomplete data

- Maintains current flexibility
- Users can choose when to validate
- Incomplete rows remain highlighted in yellow/orange for visibility

### Placeholder Display

✅ **Selected approach**: Text message (as specified in requirements)

- **EN**: "work in progress, validate to see the results"
- **FR**: "en cours jusqu'à validation"
- Clear communication of current state and required action

---

## Implementation Scope

### Components to Update

1. **ModulePage.vue** - Reorder component layout
2. **ModuleTotalResult.vue** - Add validation button, conditional display, remove decimals
3. **Co2Header.vue** - Remove validation button from header
4. **common.ts (i18n)** - Add placeholder text translations

### State Management

- Continue using existing timeline store (`timelineStore`)
- Validation states: 'default' | 'in-progress' | 'validated'
- No changes to state management logic needed

### Visual Design ([based on mockups](https://www.figma.com/proto/DXeFrKiXUpqCHUEgXVROng/200_Calculateur-CO2?page-id=45%3A833&node-id=3232-43627&viewport=-7736%2C-9881%2C0.96&t=ICbUtigbUe1Lt6fU-1&scaling=scale-down-width&content-scaling=fixed&starting-point-node-id=3232%3A43627))

- Total section uses 2-column grid layout:
  - **Left column** (content area):
    - **When validated**: 3 lines stacked vertically
      1. Label: "Total Lab Carbon Footprint" (body text, medium weight)
      2. Value: "8,950" (large bold heading)
      3. Unit: "t CO₂-eq" (small grey text)
    - **When NOT validated**: Single line
      1. Placeholder: "work in progress, validate to see the results" (body text, grey)
  - **Right column**: Validation button (vertically centered)
    - Not validated: Solid teal button "Validate Module"
    - Validated: Solid button "Edit Module"
- Background colors:
  - Not validated: Default grey background
  - Validated: Light blue/cyan background (#E0F7FA or similar)

---

## Edge Cases & Considerations

### Multiple Module Types

- **Affected modules**: Equipment (Electric Consumption), MyLab (Headcount)
- Both use the same Total section component
- Unit handling:
  - Equipment: "kg CO₂-eq" → display as "t CO₂-eq" (tons, whole numbers)
  - MyLab: "FTE" → already uses whole numbers

### Responsive Design

- 3-column grid may need adjustment on mobile screens
- Consider stacking button below value on small screens
- Test with longer French translations

### Existing Functionality Preserved

- Timeline states continue working (same store)
- Bottom navigation remains unchanged
- Table incomplete row highlighting stays the same
- Module state is still frontend-only (not persisted to backend)

---

## Success Criteria

✅ Total section appears at top of page (between Title and Charts)
✅ Total value displays whole numbers only (no decimals)
✅ When NOT validated: shows placeholder text message
✅ When validated: shows calculated total value
✅ Validation button integrated into Total section
✅ Button text toggles: "Validate Module" ↔ "Edit Module"
✅ Button styling changes based on state
✅ Header no longer shows validation button
✅ Timeline states continue to work correctly
✅ Both English and French translations work
