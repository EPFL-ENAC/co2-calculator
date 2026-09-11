---
status: accepted
issue: 2517
last_updated: 2026-09-11
title: "Inline cells: one shell per editable cell, editor mounted on activation"
summary: "Every editableInline cell of ModuleTable renders the same lightweight shell (locked or not) and mounts its Quasar editor only when activated. Replaces the negative-margin alignment hack of PR #2568 and removes the per-cell QSelect + composable cost."
---

# 2517 — Inline cells: lazy editor shell

## Problem

In the Equipment table, CSV-imported rows show their class as plain text
(the field is locked by the data-entry policy, see
[951](951-edit-rights-per-dataset-permissions.md)) while manually added rows
show a Quasar select. The two shapes have different horizontal insets, so the
Class column text was misaligned. PR #2568 (commit `b651e281c`) fixed the
symptom with a CSS hack: `$table-inline-field-padding-x` applied as
`.q-field__control` padding and cancelled by an equal negative margin on the
field wrapper. The maintainers asked for a consistent UX instead of the hack,
and for the inline-editing perf problems to be fixed in the same move.

The perf problems, measured in code rather than guessed:

- Every kind/subkind cell mounts `ModuleInlineSelect`, which instantiates
  `useEquipmentClassOptions` (three watchers, an i18n composer) and a
  `QSelect`, and rebuilds label `Map`s over the whole taxonomy in its
  computeds. Subkind cells also load the class list they never show
  (`skipClassOptions` was never passed).
- Every other inline cell mounts a `QInput`/`QSelect` even when nobody edits
  it. A 200-row page of Equipment mounts 400 selects and 400 inputs.
- `ModuleTable.vue` carried a `watch(..., () => {}, { deep: true })` over the
  whole page's rows with an empty callback.

Network was already fine: `stores/factors.ts` dedups the taxonomy request per
`(submodule, year, lang)`.

## Decision

**Lazy editor shell.** One `ModuleInlineCell.vue` wraps every
`editableInline` cell, locked or not. At idle the cell renders a lightweight
shell with fixed geometry: the display text (from `renderCell`, so labels
resolve through the table-level maps) plus a static affordance (pencil for
inputs, chevron for selects) when the cell can be edited. Activating an
editable cell (click, Enter, Space) mounts the real editor — the existing
`ModuleInlineSelect` or `QInput`/`QSelect` — with autofocus. Blur, commit or
Escape unmount it and the shell returns.

Locked cells (policy lock, or the typed-but-unused `readOnlyWhen`) and cells of
a disabled table (validated module, no EDIT permission) render the same shell
with no affordance, no hover, default cursor, normal text colour: plain text,
as today.

Alternatives rejected:

- _Keep every field mounted and render locked cells as disabled fields._
  Aligns by construction but doubles the mounted `QSelect` count; would have
  needed all the perf work as a prerequisite instead of a consequence.
- _Keep the hack._ It only exists because two different DOM shapes share a
  column; a third shape (e.g. a badge) would need a second hack.

## Component contract — `ModuleInlineCell.vue`

`frontend/src/components/organisms/module/ModuleInlineCell.vue`, no `watch`,
no `<style>` block (geometry lives in `.co2-table`, see below).

| Prop / model        | Type                  | Meaning                                               |
| ------------------- | --------------------- | ----------------------------------------------------- |
| `text`              | `string`              | idle display text                                     |
| `textIsPlaceholder` | `boolean?`            | grey placeholder rendering (new-row usage suggestion) |
| `locked`            | `boolean`             | policy / `readOnlyWhen` lock, never activates         |
| `disabled`          | `boolean`             | whole-table disable, never activates                  |
| `affordance`        | `'input' \| 'select'` | which icon the idle shell shows                       |
| `requiredEmpty`     | `boolean?`            | orange contour (#259) on the shell                    |
| `title`             | `string?`             | column hint at idle                                   |
| `ariaLabel`         | `string`              | accessible name of the button-role shell              |
| `v-model:editing`   | `boolean`             | open-editor state, owned by the parent                |
| emit `cancel`       |                       | Escape pressed in the editor                          |
| default slot        |                       | the editor, injected by `ModuleTable`                 |

State machine:

- idle → editing: `activate()` on click / Enter / Space, only when
  `!locked && !disabled`. The parent snapshots the original value.
- editing → idle (commit): the parent sets `editing = false` after
  `commitInline` resolves with no error. Selects end on pick; inputs end on
  blur. While `getError` is non-empty the parent keeps the editor open so the
  error stays visible.
- editing → idle (cancel): Escape emits `cancel`; the parent restores the
  snapshot and clears the error. Escape reaches the wrapper because `QSelect`
  only `prevent`s the key; the menu closes on the same press (QMenu listens
  on `keyup`, the wrapper on `keydown`).
- Enter inside an input editor blurs the input, which commits. Not wired for
  selects (`QSelect` consumes Enter).
- Focus return: when the idle shell re-mounts and `document.activeElement` is
  `body`, the shell focuses itself. Keyboard users land back on the cell after
  Enter/Escape; a click into another cell is not stolen because that cell's
  editor autofocuses in its own `onMounted`.

Focus does **not** activate. Tab lands on the shell (`:focus-visible`), Enter
opens. Focus-activation would open an editor on every Tab stop and loop with
the refocus-on-return. Keyboard users pay one extra keystroke per cell.

The editor is only ever closed by its own blur/commit/cancel. `QField` emits
`blur` from a `setTimeout(0)` that is cleared on unmount, so an editor
unmounted from outside never commits. Keep this invariant in #899.

## `ModuleTable.vue` wiring

- Template: the locked `<span>` branch, the `inline-input--required-empty`
  class binding and the `#append` pencil are gone. `<module-inline-cell>`
  wraps the two editor kinds; kind/subkind columns keep `ModuleInlineSelect`
  (now with `open-on-mount`, `@committed`, `@blur`), other columns keep
  `<component :is="col.inputComponent">` with `autofocus` and a function ref
  that opens plain `QSelect` menus on mount.
- Script: `inlineEditing` record keyed by the existing `errorKey(row, col)`
  holding the original value; `beginInlineEdit` / `endInlineEdit` /
  `cancelInlineEdit`; `onInlineInputBlur` (commit, then end only without
  error); `onInlineSelectPicked` (end, then commit); `isInlineLocked`;
  `inlineCellText` (placeholder for required-empty usage cells, otherwise
  `renderReadOnlyInlineCell`, so the new-row factor autofill still fires at
  idle).
- `commitInline` returns early when the value equals the snapshot. An
  unchanged blur no longer sends a PATCH.
- The no-op deep watcher is deleted.
- `getColumnClasses` adds `co2-table__td--inline` on inline columns so the td
  drops its horizontal padding and the shell carries the inset.

## Editor-side changes

- `VirtualSelectField.vue` exposes `showPopup()`.
- `ModuleInlineSelect.vue`: prop `openOnMount`; emits `blur` and
  `committed` (emitted right after the local model write, before the awaited
  PATCH, so the shell returns immediately and the PATCH continues on the row);
  `onMounted` awaits the option load (class, subclass, or the building's
  rooms) then opens the menu — `QSelect.showPopup` opens nothing when the
  option list is still empty; `skipClassOptions` for subkind editors; the
  subclass "-" placeholder branch is deleted (the shell shows `-` at idle; an
  activated subkind with no options is an empty select the user blurs out of,
  where a non-focusable placeholder would have left the cell stuck open).

## Geometry and tokens

- `td.co2-table__td--inline` has zero horizontal padding; the shell and the
  editor control both use `padding: 0 $table-inline-field-padding-x`. That
  token and the plain td padding (`$spacing-md`) both resolve to
  `opt.$tokens-spacing-12`, so text of inline and non-inline columns sits on
  the same grid with no negative margin.
- New tokens: `$table-inline-field-height` (2.5rem, the Quasar dense field
  control height, as shell `min-height` and editor control `height`) and
  `$table-inline-icon-size` (the pencil).
- Deleted from `.co2-table`: the transparent-outline rule, the field hover
  rule, the hack block, `field-sizing: content`, the append padding, the
  required-empty width rules, `.inline-edit-icon`, the dropdown-icon and
  select-cursor rules; from the scoped block, the two
  `.inline-input--required-empty :deep(...)` rules.
- Rules are unscoped under `.co2-table` and reach the child component. A
  future consumer of `ModuleInlineCell` outside `.co2-table` gets no geometry;
  acceptable while it is table-only.

## Behaviour changes

- Unchanged blur / Tab / Escape no longer PATCHes. A failed server PATCH is
  retried by editing the value again; Escape reverts.
- The pencil shows on empty editable input cells too (today `hasValue` hid it).
- The idle hover highlight spans the full cell width; the editor fills the
  cell (no more content-hugging fields).
- Keyboard: Tab stops on editable cells, Enter/Space opens, Enter commits an
  input, Escape cancels and returns focus to the cell.

## Perf: done here vs deferred to #899

Here: at most one mounted editor per table instead of one per cell; the
no-op deep watcher is gone; subkind editors skip the class list; unchanged
blurs skip the PATCH.

Deferred to #899 (`useModuleTableColumns` / `useInlineCellEditing`,
[1557](1557-moduletable-decomposition.md)): per-cell allocations in
`getColumnRules` / `getColumnClasses` / `getColumnStyle`; the label `Map`
rebuilds in `ModuleInlineSelect` (once per activation now, moot);
`moduleStore.getSubmoduleTaxonomy` bypassing the factors-store cache; virtual
scroll for the 1000-row page size.

## Quasar facts relied on (2.24)

- `autofocus` is a `QField` prop, applied in `onMounted`
  (`composables/private.use-field/use-field.js`).
- `QField` `blur` fires from a `setTimeout(0)` in `onControlFocusout`, is
  suppressed while a popup is open, and the timer is cleared on unmount.
- `QSelect.showPopup()` focuses the field, then runs the `@filter` callback
  when one is bound, otherwise opens the menu only if `options` is non-empty
  (`components/select/QSelect.js`).
- Picking an option hides the popup and refocuses the field: no `blur`
  follows a pick. Dismissing the menu by clicking outside does emit `blur`.
- `QSelect` calls `prevent` (not `stop`) on Escape; `QMenu` closes on window
  `keyup`.

## Verification

Manual, with the local stack (backend + `quasar dev`, test login):

1. Equipment IT table with CSV and manual rows: imported class/name cells are
   plain text, default cursor, no hover; imported sub-class/usage cells and
   every manual cell show pencil/chevron and hover. Text left edges align
   down the column and with the Name column.
2. Usage cell: click, type `12,5`, Tab: the error stays and the editor stays.
   Fix to `12.5`, Enter: one PATCH, the shell shows the value. Escape on a
   dirty cell reverts with no PATCH. Blur without a change sends no PATCH.
3. Sub-class cell: one click opens the menu once the options are loaded; a
   pick updates the shell and PATCHes; open then click outside returns to the
   shell with no PATCH.
4. New-row usage cell: grey suggested value with the orange contour at idle;
   edit and save, the row leaves the new-row emphasis.
5. Buildings rooms: the room menu lists the building's rooms; a pick also
   updates the room-type cell. Headcount: `sius_code` opens on click, name
   commits on Enter.
6. Validate the module: every inline cell is plain text and Tab skips them.
   Explorer and Planner tables stay editable.
7. `make lint`, `make type-check`, `npm run test-ct` in `frontend/`. The e2e
   specs serve `dist/spa`: rebuild before `npm run test:e2e`.

## Commits

1. `docs: plan for #2517 inline cell lazy editor`
2. `feat(table): add ModuleInlineCell shell`
3. `refactor(table): prepare inline editors for lazy mount`
4. `feat(table): mount inline editors lazily behind ModuleInlineCell (#2517)`
