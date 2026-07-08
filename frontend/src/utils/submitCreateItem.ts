/**
 * Coupling logic for "create item then refresh" submodule forms (#1463).
 *
 * `postItem` (src/stores/modules.ts) does the create POST, then chains a
 * series of unrelated follow-up refreshes (totals, submodule data, trips
 * map, breakdown, module states). If the create POST succeeds but any of
 * those follow-ups rejects, the whole call rejects too — even though the
 * item already exists server-side.
 *
 * `submitCreateItem` isolates that distinction so callers can react
 * correctly: `onCreated` fires as soon as the create POST itself succeeds
 * (independent of the trailing refreshes), `onRefreshFailed` fires if a
 * refresh fails afterwards, and `onCreateFailed` fires only when the create
 * POST itself failed.
 */
export interface SubmitCreateItemActions {
  onCreated: () => void;
  onRefreshFailed: (err: unknown) => void;
  onCreateFailed: (err: unknown) => void;
}

export async function submitCreateItem(
  postItem: (onCreated: () => void) => Promise<void>,
  actions: SubmitCreateItemActions,
): Promise<void> {
  let created = false;
  try {
    await postItem(() => {
      created = true;
      actions.onCreated();
    });
  } catch (err: unknown) {
    if (created) {
      actions.onRefreshFailed(err);
      return;
    }
    actions.onCreateFailed(err);
  }
}
