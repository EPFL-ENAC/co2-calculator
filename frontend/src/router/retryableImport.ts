// A lazy download shared by every caller until it fails. A failure is
// forgotten, so the next navigation downloads again instead of getting the
// old rejection.
export function retryableImport<T>(load: () => Promise<T>) {
  let pending: Promise<T> | null = null;
  const get = (): Promise<T> => {
    pending ??= load().catch((e: unknown) => {
      pending = null;
      throw e;
    });
    return pending;
  };
  // Starts the download early. The navigation that awaits `get` reports a
  // failure, so the early call only marks the promise as observed.
  const preload = (): void => {
    get().catch(() => undefined);
  };
  return { get, preload };
}
