// Fails the type check when the theme names drift (#3244).
//
// docker/entrypoint.sh lists the names a theme.conf may set, and the SCSS
// reads them as var(--theme-<name>). A name only in the SCSS can never be
// set; a name only in the script is accepted but changes nothing. Neither
// errors at runtime, so this check is the only place the drift shows.
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const FRONTEND = new URL('../', import.meta.url).pathname;

const script = readFileSync(join(FRONTEND, 'docker/entrypoint.sh'), 'utf8');
// String search, not one regex over the call: a list spans quoted,
// backslash-continued lines, and a regex for that backtracks badly.
const list = (array) => {
  const end = script.indexOf(`, ${array}, " ")`);
  const start = script.lastIndexOf('split(', end);
  if (start === -1 || end === -1) {
    throw new Error(`docker/entrypoint.sh: no split("...", ${array}) list`);
  }
  return [...script.slice(start, end).matchAll(/"([^"]*)"/g)]
    .map((m) => m[1])
    .join('')
    .split(/\s+/)
    .filter(Boolean);
};
// The font names are not here: they become @font-face rules, not variables.
const known = new Set([...list('colors'), ...list('lengths')]);

const files = readdirSync(join(FRONTEND, 'src'), { recursive: true })
  .filter((file) => /\.(scss|vue)$/.test(file))
  .map((file) => join(FRONTEND, 'src', file));
const used = new Set();
for (const file of files) {
  for (const [, name] of readFileSync(file, 'utf8').matchAll(
    /--theme-([a-z0-9-]+)/g,
  )) {
    used.add(name);
  }
}

const unknown = [...used].filter((name) => !known.has(name));
const unused = [...known].filter((name) => !used.has(name));
if (unknown.length || unused.length) {
  console.error(
    [
      unknown.length && `SCSS reads names entrypoint.sh refuses: ${unknown}`,
      unused.length && `entrypoint.sh accepts names no SCSS reads: ${unused}`,
    ]
      .filter(Boolean)
      .join('\n'),
  );
  process.exit(1);
}
console.log(`theme keys: ${known.size} names, SCSS and entrypoint.sh agree`);
