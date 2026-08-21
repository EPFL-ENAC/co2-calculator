/**
 * Poll a deferred plan-prefill job until it reaches its terminal state.
 *
 * The plan PATCHes persist their metadata change immediately and hand the
 * copy of a reference year into the plan years to a background job
 * (backend plan #2050 Track F4). Until that job finishes the year sections
 * exist but are empty, so the caller must wait before rendering them.
 */

export interface PrefillStatusLike {
  finished: boolean;
}

/** First poll delay, ms — most prefills finish inside one of these. */
const INITIAL_DELAY_MS = 500;
/** Ceiling, ms — a multi-minute prefill must not poll twice a second. */
const MAX_DELAY_MS = 3000;
const BACKOFF_FACTOR = 1.5;

export async function pollUntilPrefilled<T extends PrefillStatusLike>(
  fetchStatus: () => Promise<T>,
  sleep: (ms: number) => Promise<void> = (ms) =>
    new Promise((resolve) => setTimeout(resolve, ms)),
): Promise<T> {
  let delay = INITIAL_DELAY_MS;
  for (;;) {
    const status = await fetchStatus();
    if (status.finished) {
      return status;
    }
    await sleep(delay);
    delay = Math.min(delay * BACKOFF_FACTOR, MAX_DELAY_MS);
  }
}
