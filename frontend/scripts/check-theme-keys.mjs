// Fails the type check when the theme names drift (#3244).
//
// docker/theme.awk lists the names a theme.conf may set, and the SCSS reads
// them as var(--theme-<name>). A name only in the SCSS can never be set; a
// name only in theme.awk is accepted but changes nothing. Neither errors at
// runtime, so this check is the only place the drift shows.
import { readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';

const FRONTEND = new URL('../', import.meta.url).pathname;

const awk = readFileSync(join(FRONTEND, 'docker/theme.awk'), 'utf8');
// String search, not one regex over the call: the list spans quoted,
// backslash-continued lines, and a regex for that backtracks badly.
const start = awk.indexOf('split(');
const end = awk.indexOf(', names', start);
if (start === -1 || end === -1) {
  throw new Error('docker/theme.awk: no split("...", names) list');
}
const known = new Set(
  [...awk.slice(start, end).matchAll(/"([^"]*)"/g)]
    .map((m) => m[1])
    .join('')
    .split(/\s+/)
    .filter(Boolean),
);

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
      unknown.length && `SCSS reads names theme.awk refuses: ${unknown}`,
      unused.length && `theme.awk accepts names no SCSS reads: ${unused}`,
    ]
      .filter(Boolean)
      .join('\n'),
  );
  process.exit(1);
}
console.log(`theme keys: ${known.size} names, SCSS and theme.awk agree`);
