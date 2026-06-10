# PR #1308 — Code Review (max effort, scaled to PR size)

**PR**: `feat: Add columnSize support to module table` by @BenBotros
**Branch**: `feat/1233-responsiveness-of-tables` (rebased + force-pushed)
**Scope**: 9 files, +62/-16 — closes #1233
**Effort calibration**: 5 finder angles (not 9) — proportional to 62-line diff per karpathy "simplicity first".

## Verdict: REQUEST CHANGES — verified semantic regression on at least 3 columns

The token-extraction refactor is a good idea executed with a subtle but verifiable bug: **the migration silently inverts the semantics of any column that previously used `maxColumnWidth` (cap) when it's replaced with `columnSize` (floor)**, because `getColumnStyle` only wires `columnSize` to `--min-column-width`, never to `--max-column-width`. At least 3 columns in this PR are migrated this way and will resize differently than before.

## P0 — Verified semantic regressions

### F1. `columnSize` is a min-width-only token, but the PR uses it to replace `maxColumnWidth` caps

**Evidence** (`ModuleTable.vue:1167-1178` post-change):

```ts
function getColumnStyle(col: TableViewColumn) {
  const style: Record<string, string> = {};
  const minWidth =
    col.minColumnWidth ??
    (col.columnSize !== undefined ? COLUMN_SIZES[col.columnSize] : undefined);
  if (minWidth !== undefined) {
    style["--min-column-width"] = `${minWidth}px`;
  }
  if (col.maxColumnWidth !== undefined) {
    style["--max-column-width"] = `${col.maxColumnWidth}px`;
  }
  return style;
}
```

`columnSize` only contributes to MIN. There is no `--max-column-width` from `columnSize`. So replacing `maxColumnWidth: N` with `columnSize: 'md'` does not preserve the cap.

**Verified parity violations in the diff**:

| File:line                                 | Before                           | After                                | Behavior change                                                                                                                             |
| ----------------------------------------- | -------------------------------- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| `purchase.ts:46` (category)               | `maxColumnWidth: 200` (cap only) | `columnSize: 'md'` (160 min, no max) | **Semantic inversion**: column was capped at 200px, now floored at 160px with no upper bound — can grow unboundedly with long option labels |
| `buildings.ts:46` (room_type)             | `min=max=150` (fixed)            | `columnSize: 'md'` (160 min, no max) | Lost fixed-width behavior + 10px wider; previously locked, now resizable upward with no cap                                                 |
| `buildings.ts:85` (room_allocation_ratio) | `minColumnWidth: 140`            | `columnSize: 'md'` (160 min)         | Silent +20px width bump                                                                                                                     |

**Consequence**: User-visible column-width changes that don't match the previous design intent. Adjacent columns re-flow on wide screens; the previously-careful 1/3 + 1/6 + 1/6 grid layouts in `buildings.ts` break.

**Fix options**:

- **(a) Add `maxColumnWidth` semantics to `columnSize`**: have `columnSize` set both `--min-column-width` AND `--max-column-width` to the same value, making it a "fixed at N" token. This mirrors the old `min=max=150` pattern from buildings.ts.
- **(b) Restore each migrated column's original behavior**: for `purchase.ts:46`, use `maxColumnWidth: 200`; for `buildings.ts:46`, use both `minColumnWidth: 150` and `maxColumnWidth: 150`; for `buildings.ts:85`, use `minColumnWidth: 140`. Then keep the `columnSize` token only for new columns or columns that genuinely have no prior cap.
- **(c) Split the token**: `columnSize` (min), `columnMaxSize` (max), `columnFixedSize` (min=max). More explicit.

Option (a) is the cleanest if the design system genuinely wants "fixed-width tokens"; option (b) is the most surgical if the PR's intent was just to extract a shared scale.

---

### F2. Action column now reserves 120px where it was previously fluid

**Evidence**: `ModuleTable.vue:873` adds `columnSize: 'sm'` to the synthesized action column, where it previously had `minColumnWidth: undefined, maxColumnWidth: undefined`.

**Consequence**: The action column used to shrink to fit its icon-button content. Now it reserves 120px minimum, squeezing data columns on narrow viewports or tables with many columns.

**Fix**: Drop `columnSize: 'sm'` from the action column unless this is a deliberate UX decision (in which case, mention it in the PR description and verify it on narrow viewports).

## P1 — Migration completeness gaps

### F3. Mixed convention within the same file — buildings.ts

**Evidence**: 4 fields at `buildings.ts:98, 111, 124, 137` still use raw `maxColumnWidth: 120` (no `columnSize`, no `minColumnWidth`). 5 sibling fields in the same file are migrated to `columnSize`.

**Consequence**: Double source of truth. If `COLUMN_SIZES.sm` is bumped from 120 to 128, the 5 migrated fields shift but the 4 raw-pixel fields stay at 120 — same module renders with two different "sm" widths. Future contributors copy whichever pattern is nearest, accelerating drift.

**Fix**: Either migrate the orphans (`maxColumnWidth: 120` → introduce a `columnMaxSize: 'sm'` token if F1 fix (c) is chosen), OR explicitly document that `maxColumnWidth` remains the canonical API for caps.

### F4. Same in equipment-electr ic-consumption.ts — plus a semantic gap in the token scale

**Evidence**: 4 fields at lines 74, 92, 119, 139 still use `maxColumnWidth: 200/150`. Crucially: the value `150` has NO equivalent in `COLUMN_SIZES` (xs:80 / sm:120 / md:160 / lg:200 / xl:260) — there is no token between sm and md.

**Consequence**: Even if the author wanted to migrate these, they couldn't losslessly. Either snap 150 to md (160 — silent +10px) or to sm (120 — silent -30px), or keep using raw pixels. The token scale has a gap that prevents full migration.

**Fix**: Add a token (e.g. `smd: 140` or similar) OR explicitly mark some columns as "intentionally not in the token scale" and document why.

### F5. Type still exposes `minColumnWidth` AND `maxColumnWidth` alongside `columnSize` — violates project's no-backward-compat rule

**Evidence**: `moduleConfig.ts` keeps both old props on `ModuleField` with no `@deprecated` marker. Per project memory `feedback_no_backward_compat.md` (pre-v1.x: "remove old paths when new ships"), dual API shouldn't coexist.

**Consequence**: New module configs see three equivalent ways to set width with no signal which is canonical. Migration ossifies at ~70% done.

**Fix options**:

- Remove the raw props (forces migration of all orphans). May not be feasible if some columns genuinely need both min AND max with different values.
- Apply F1 fix (c) to split the token cleanly: `columnSize` (min only), `columnMaxSize` (max only), and remove `minColumnWidth`/`maxColumnWidth` entirely.
- At minimum, add `@deprecated` JSDoc to `minColumnWidth` / `maxColumnWidth` so IDE flags them.

## P2 — Architecture / scope

### F6. `_q-table.scss` global padding changes affect ALL q-tables, not just `ModuleTable`

**Evidence**: The 6-line SCSS change in `_q-table.scss` modifies global QTable padding (4px 2px → 4px; first/last child 16px → 8px). Affects every QTable in the app, including `YearSelector`, `UnitsTable`, `UnitDialogue`, `SimulationsPage`, `DocumentationEditingPage`, `UITextsEditingPage`.

**Consequence**: Out-of-scope visual changes on tables that weren't tuned to the new spacing. Could cause overflows or misalignments in components not mentioned in the PR description.

**Fix**: Either scope the SCSS to `.module-table` (or whatever ModuleTable's root class is), OR explicitly mention in the PR description which other tables were intentionally updated.

### F7. Naming collision: `COLUMN_SIZES` reuses `xs/sm/md/lg/xl` already bound to `$spacing-*`

**Evidence**: `frontend/src/css/02-tokens/_decisions.scss:21-27` already binds `xs/sm/md/lg/xl` to `$spacing-*` (4/8/12/16/24 px). The new TS map uses the same alias for column widths (80/120/160/200/260 px). Two parallel scales, same names, completely different meanings.

**Consequence**: Future reader trap. A maintainer reading `columnSize: 'sm'` reasonably assumes it maps to the same `sm` as everything else.

**Fix**: Either rename (`columnSize: 'narrow' | 'medium' | 'wide' | ...`) OR fold into the SCSS token system (see F8).

### F8. CSS-in-JS antipattern — column widths belong in SCSS

**Evidence**: PR computes per-cell inline `--min-column-width` style attribute in `getColumnStyle()`. The SCSS layer already has `.column-min-width { min-width: var(--min-column-width, 100%); }` consuming it. The token pipeline (`02-tokens/_decisions.scss` → `_components.scss` → `css-properties.scss`) is established for `$table-padding-x/y/gap` — column widths could live there.

**Right altitude**: Declare the scale in `02-tokens/_components.scss` (`$table-column-width-xs: 80px`, etc.), surface via CSS custom properties (`--semantic-column-width-md`), and consume in `_q-table.scss` via class names (`<td class="column-size-md">`). Browser handles the resolution; no per-cell inline style.

**Consequence today**: Two-language sizing decision splits the design system. Token-aware tooling (linters, Style Dictionary, theming) only sees the SCSS side and misses the TS values.

### F9. Truthy → `!== undefined` is patching a type-system gap

**Evidence**: Three guard sites changed (`ModuleTable.vue:74, 1170, 1184`). The fix defends against `0` being treated as missing.

**Consequence**: With `columnSize: ColumnSize` typed as `'xs'|'sm'|'md'|'lg'|'xl'`, the type system already excludes `0`. The runtime check is necessary only because the raw `minColumnWidth?: number` and `maxColumnWidth?: number` props remain. If F5 (remove raw props) is fixed, F9 disappears automatically — typed unions narrow at compile time.

### F10. Inline template expression duplicates `getColumnClasses` logic

**Evidence**: The expression `col.minColumnWidth !== undefined || col.columnSize !== undefined` appears inline in the template (`ModuleTable.vue:74`) AND as `hasMinWidth` in `getColumnClasses`. Drift risk.

**Fix**: Use one source. Either extract a `hasMinWidth(col)` helper called from both, or move the entire class computation into `getColumnClasses` and reference its result from the template via a computed.

## Karpathy checklist

| Question                                  | Answer                                                                                             |
| ----------------------------------------- | -------------------------------------------------------------------------------------------------- |
| Satisfies original requirements?          | **Partial.** Token extraction works, but introduces verifiable behavior changes on 3 columns (F1). |
| Edge cases covered?                       | F1 — the migration spec's semantic gap (cap vs floor) wasn't considered.                           |
| APIs / framework calls real?              | Yes.                                                                                               |
| Auth / security?                          | N/A.                                                                                               |
| Simpler than necessary or overengineered? | Token map is the right shape; the value placement (TS vs SCSS) is questionable (F8).               |
| Duplicated / dead code?                   | Yes — mixed conventions (F3, F4), template/function duplication (F10).                             |
| Naming / typing accurate?                 | F7 — naming collision with existing token scale.                                                   |
| Performance / scalability?                | N/A — UI refactor.                                                                                 |
| Tests for happy path / edges?             | **No tests added.** A visual-regression snapshot would have caught F1, F2, F3.                     |
| Would I approve from a junior?            | **No.** Request F1 + F2 minimum. F3-F5 strongly recommended.                                       |

## Recommended action

**Request changes.** Required before merge:

1. **F1**: fix the cap-vs-floor semantic regression. Pick fix (a), (b), or (c) per the options above. Personal recommendation: option (c) — split `columnSize` (min) and `columnMaxSize` (max) so the token semantics are explicit, and migrate all three current uses to whichever is correct.
2. **F2**: confirm whether the action column should genuinely have a 120px minimum, or drop the `columnSize: 'sm'` addition.
3. **F3 + F4**: either fully migrate the orphan columns in `buildings.ts` and `equipment-electric-consumption.ts`, or document that raw pixel widths remain canonical (the latter would invalidate much of the PR's purpose).
4. **F5**: mark `minColumnWidth` and `maxColumnWidth` `@deprecated` if dual API stays, or remove them entirely if F1 fix (c) is chosen.

Strongly recommended:

- **F6**: scope the `_q-table.scss` changes or document the cross-table intent.
- **F10**: dedupe the class-computation logic.

Follow-up (this PR or next):

- **F7 + F8**: fold the token scale into the SCSS design system; rename to avoid the spacing-token name collision.
