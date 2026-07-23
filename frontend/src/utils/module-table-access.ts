/**
 * Who may interact with a module table's rows, across the three contexts a
 * table renders in: Calculator, Explorer and Planner.
 *
 * The Calculator locks a module once it is validated, which the timeline store
 * (`stores/modules.ts`) carries. That store tracks a *single* carbon report and
 * cannot represent the two simulators: the Explorer has no validated state at
 * all, and a plan holds one report per year. A Validated state read there while
 * an Explorer or Planner table is on screen belongs to the Calculator report of
 * the selected workspace year — never to the table being rendered.
 */
export interface ModuleTableAccess {
  /** Simulator Explorer (`SimulationExplorePage`). */
  isExplorer: boolean;
  /** Simulator Planner — the table addresses a plan-year report by id. */
  isPlanner: boolean;
  /** Module EDIT permission; mirrors the backend gate on every write route. */
  canEdit: boolean;
  /** Parent-driven lock: Planner Active toggle, deactivated inputs. */
  disable: boolean;
  /** Calculator timeline state for this module. */
  isValidated: boolean;
}

/** Editing, inline edits, row deletion and the Planner % slider. */
export function isModuleTableDisabled(ctx: ModuleTableAccess): boolean {
  if (ctx.isExplorer) return false;
  if (ctx.disable || !ctx.canEdit) return true;
  if (ctx.isPlanner) return false;
  return ctx.isValidated;
}

/**
 * The per-row Comment button. Notes stay available on read-only tables, so
 * `disable` does not block them — only permission and, in the Calculator, the
 * validated lock.
 */
export function isModuleNoteDisabled(ctx: ModuleTableAccess): boolean {
  if (!ctx.canEdit) return true;
  if (ctx.isExplorer || ctx.isPlanner) return false;
  return ctx.isValidated;
}
