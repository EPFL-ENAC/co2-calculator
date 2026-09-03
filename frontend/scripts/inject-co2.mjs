// Computes the first-load weight of the built SPA (index.html, the
// entry/preload assets it references, and the woff2 fonts those load) and
// bakes it into index.html as a <meta name="co2-first-load"> tag the app reads
// at runtime.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

// websitecarbon.com-derived average, grams of CO₂ per transferred byte.
const G_PER_BYTE = Number(process.env.CO2_G_PER_BYTE ?? '1.94e-7');

const distDir = resolve(dirname(fileURLToPath(import.meta.url)), '../dist/spa');
const indexPath = join(distDir, 'index.html');

let html = readFileSync(indexPath, 'utf8');
html = html.replace(/<meta name="co2-first-load" content="[^"]*">/gi, '');

const attrUrl = (tag) =>
  tag
    .match(/\b(?:src|href)=(?:"([^"]+)"|'([^']+)'|([^\s>]+))/i)
    ?.slice(1)
    .find(Boolean);

const textAssets = new Set();
const fontAssets = new Set();
for (const [rawTag] of html.matchAll(/<(?:script|link)\b[^>]*>/gi)) {
  const url = attrUrl(rawTag);
  if (!url) continue;
  const tag = rawTag.toLowerCase();
  const isEntryScript =
    tag.startsWith('<script') && /\btype=["']?module\b/.test(tag);
  const isPreloadOrCss = /\brel=["']?(?:modulepreload|stylesheet)\b/.test(tag);
  const isFontPreload =
    /\brel=["']?preload\b/.test(tag) && /\bas=["']?font\b/.test(tag);
  if (isEntryScript || isPreloadOrCss) textAssets.add(url);
  else if (isFontPreload) fontAssets.add(url);
}
if (textAssets.size === 0) {
  throw new Error(`no first-load assets found in ${indexPath}`);
}

const readAsset = (url) => readFileSync(join(distDir, url.replace(/^\//, '')));
const gzippedBytes = (buffer) => gzipSync(buffer, { level: 9 }).length;

let totalBytes = gzippedBytes(Buffer.from(html));
for (const url of textAssets) {
  const buffer = readAsset(url);
  totalBytes += gzippedBytes(buffer);
  if (url.endsWith('.css')) {
    for (const [, fontUrl] of buffer
      .toString('utf8')
      .matchAll(/url\(["']?([^"')]+\.woff2)(?:[?#][^"')]*)?["']?\)/gi)) {
      fontAssets.add(fontUrl);
    }
  }
}
// woff2 is already Brotli-compressed, so fonts count at their raw size.
for (const url of fontAssets) {
  totalBytes += readAsset(url).length;
}

const mg = totalBytes * G_PER_BYTE * 1000;
const kb = totalBytes / 1024;

const meta = `<meta name="co2-first-load" content="${mg.toFixed(1)}|${kb.toFixed(1)}">`;
if (!html.includes('</head>')) {
  throw new Error(`no </head> in ${indexPath}`);
}
writeFileSync(indexPath, html.replace('</head>', `${meta}</head>`));

console.log(
  `co2-first-load: ${kb.toFixed(1)} KB (${textAssets.size + 1} files + ${fontAssets.size} fonts) → ${(mg / 1000).toFixed(2)} g CO₂`,
);
