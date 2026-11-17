// Writes a .gz (gzip 9) and a .br (brotli 11) file next to each text file of
// a built SPA folder: node build/precompress.mjs dist/spa
//
// Why this exists: the file names carry a content hash and never change, so
// the image compresses them once, at the highest level, and nginx sends them
// as they are (see nginx.conf: gzip_static and the .br locations). The
// Dockerfile runs this after the build; the pod root filesystem is
// read-only, so it cannot run at startup.
import { readdirSync, readFileSync, writeFileSync } from 'node:fs';
import { extname, join, resolve } from 'node:path';
import { brotliCompressSync, constants, gzipSync } from 'node:zlib';

// Text only: woff2, png and ico are compressed formats already.
const TEXT = new Set(['.js', '.mjs', '.css', '.html', '.json', '.svg', '.csv']);

if (!process.argv[2]) throw new Error('usage: precompress.mjs <dist dir>');
const distDir = resolve(process.argv[2]);
const total = { count: 0, plain: 0, gzip: 0, brotli: 0 };

// Keep a compressed copy only when it is smaller: nginx then sends the plain
// file. No size floor, the first screen loads many chunks under 1 KB.
function write(file, raw, compressed, key) {
  if (compressed.length >= raw.length) return;
  writeFileSync(file, compressed);
  total[key] += compressed.length - raw.length;
}

for (const entry of readdirSync(distDir, {
  recursive: true,
  withFileTypes: true,
})) {
  if (!entry.isFile() || !TEXT.has(extname(entry.name))) continue;
  const file = join(entry.parentPath, entry.name);
  const raw = readFileSync(file);
  total.count += 1;
  total.plain += raw.length;
  total.gzip += raw.length;
  total.brotli += raw.length;
  write(`${file}.gz`, raw, gzipSync(raw, { level: 9 }), 'gzip');
  const br = brotliCompressSync(raw, {
    params: {
      [constants.BROTLI_PARAM_QUALITY]: 11,
      [constants.BROTLI_PARAM_SIZE_HINT]: raw.length,
    },
  });
  write(`${file}.br`, raw, br, 'brotli');
}
// An empty run means the build output moved: fail the image build.
if (total.count === 0) throw new Error(`no file to compress in ${distDir}`);
console.log(
  `[precompress] ${total.count} files: ${total.plain} bytes plain, ` +
    `${total.gzip} gzip 9, ${total.brotli} brotli 11`,
);
