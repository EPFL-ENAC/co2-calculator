import { defineBoot } from '#q-app';

// A tab in the background gets no animation frame: never wait longer.
const MAX_WAIT_MS = 100;

// index.html draws a static first frame (#shell) on the login route. The app
// removes it when it mounts. On a fast connection the app can mount before
// the browser has shown that frame, and the login page then starts blank.
// Two animation frames make sure that the frame reached the screen.
// The frame stays while #q-app is empty. Called when the login title is
// wrong for what comes next: a signed-in visitor, or a chunk that failed.
export function clearFirstFrame(): void {
  document.getElementById('shell')?.replaceChildren();
}

export default defineBoot(async () => {
  if (!document.getElementById('shell')?.textContent) return;
  await new Promise<void>((resolve) => {
    requestAnimationFrame(() => requestAnimationFrame(() => resolve()));
    setTimeout(resolve, MAX_WAIT_MS);
  });
});
