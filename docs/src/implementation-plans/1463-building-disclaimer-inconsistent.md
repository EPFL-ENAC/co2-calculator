---
status: delivered
issue: 1463
last_updated: 2026-07-07
title: "Buildings room-add disclaimer fires inconsistently"
summary: "The Archibus disclaimer toast is coupled to the entire postItem() promise, including unrelated downstream refresh calls, so any transient failure among them silently suppresses the disclaimer even though the room was created."
---

# Buildings room-add disclaimer fires inconsistently

## Problem

Two "principal user" testers add a room via the Buildings module. Tester 1
sees the Archibus disclaimer toast; tester 2, same role, same action, does
not. There is no role or permission gating on this notification — the
inconsistency has a different root cause.

## Design

The disclaimer is a Quasar `Notify.create` toast fired in
`frontend/src/components/organisms/module/SubModuleSection.vue`
(`submitForm`, around line 374-387):

```ts
try {
  await moduleStore.postItem(...);
  if (props.submodule.notifyInfoOnAddKey) {
    Notify.create({ type: 'info', message: t(props.submodule.notifyInfoOnAddKey) });
  }
} catch (err: unknown) {
  // sets a form field error on 'user_institutional_id' — a field that
  // does not exist on the rooms form, so this branch is silent for rooms
  formRef.value?.setFieldError('user_institutional_id', message);
}
```

`notifyInfoOnAddKey` is statically configured for the `Building` (rooms)
submodule in `frontend/src/constant/module-config/buildings.ts:248`, and the
`item` computed in `SubModuleSection.vue:331-336` is `null` for any module
other than `headcount`/`student` — so buildings always takes the `postItem`
(create) branch. **The disclaimer is not conditioned on role, on a room
source/origin flag, or on new-vs-edit.** It fires only if the `await
moduleStore.postItem(...)` promise resolves without throwing.

`postItem` (`frontend/src/stores/modules.ts:645-757`) does far more than the
POST that creates the room. After the create call succeeds, it sequentially
`await`s a chain of unrelated side effects still inside the same `try`:
`getModuleTotals`, `getSubmoduleData`, `refreshProfessionalTravelTripsMap`,
`invalidateValidatedTotals`/`invalidateEmissionBreakdown`,
`refreshEmissionBreakdownIfNeeded`, `refreshTopClassBreakdownIfNeeded`,
`refreshModuleStates`. If **any** of these throws — a transient network
blip, a stale/aborted request from rapid navigation, a 5xx on an unrelated
totals endpoint — the whole `postItem` call rejects even though the room was
already created server-side. `submitForm`'s `catch` then swallows the error
into a form-field error that doesn't apply to rooms, so nothing is shown to
the user: no disclaimer, no error, room silently present in the table on
next reload.

**Hypothesis**: tester 2 hit exactly this — the room POST succeeded, one of
the trailing refresh calls in `postItem` failed/raced, the promise rejected,
`submitForm`'s success branch (and its `Notify.create`) never ran. This
reads as "random" because it depends on network timing / concurrent
requests, not on role, permissions, or any per-room data flag.

## Steps

- [ ] Reproduce: add a room while throttling network or forcing one of the
      post-create refresh calls (`getModuleTotals`, `getSubmoduleData`, etc.)
      to reject (e.g. via a temporary mock/breakpoint), and confirm the room
      is created but no disclaimer toast appears — confirming the
      hypothesis before touching code.
- [ ] Decouple the disclaimer from the full `postItem` promise: fire it
      immediately after the create POST succeeds (before the trailing
      refresh chain), not after every downstream refresh resolves.
- [ ] Decide error-recovery UX for a failed downstream refresh after a
      successful create — at minimum surface a visible error/toast instead
      of silently setting a field error on a non-existent form field
      (`user_institutional_id` is headcount-specific, not a rooms field).
- [ ] Add a regression test around `submitForm`/`postItem` asserting the
      disclaimer fires whenever the create call itself succeeds, independent
      of whether trailing refresh calls (totals/breakdown/states) succeed or
      fail.
- [ ] Verify manually: add a room with a forced failure in one trailing
      refresh call and confirm the disclaimer still shows.
