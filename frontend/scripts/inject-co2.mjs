// Computes the gzipped first-load weight of the built SPA (index.html plus the
// entry/preload assets it references) and bakes it into index.html as a
// <meta name="co2-first-load"> tag the app reads at runtime.
import { readFileSync, writeFileSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';

// websitecarbon.com-derived average, grams of CO₂ per transferred byte.
const G_PER_BYTE = Number(process.env.CO2_G_PER_BYTE ?? '1.94e-7');

const distDir = resolve(dirname(fileURLToPath(import.meta.url)), '../dist/spa');
const indexPath = join(distDir, 'index.html');

let html = readFileSync(indexPath, 'utf8');
html = html.replace(/<meta name="co2-first-load" content="[^"]*">/g, '');

const assetPaths = [];
for (const [tag] of html.matchAll(/<(?:script|link)\b[^>]*>/g)) {
  const isEntryScript =
    tag.startsWith('<script') && tag.includes('type="module"');
  const isPreloadOrCss =
    tag.includes('rel="modulepreload"') || tag.includes('rel="stylesheet"');
  if (!isEntryScript && !isPreloadOrCss) continue;
  const url = tag.match(/(?:src|href)="([^"]+)"/)?.[1];
  if (url) assetPaths.push(url);
}
if (assetPaths.length === 0) {
  throw new Error(`no first-load assets found in ${indexPath}`);
}

const gzippedBytes = (buffer) => gzipSync(buffer, { level: 9 }).length;

let totalBytes = gzippedBytes(Buffer.from(html));
for (const path of assetPaths) {
  totalBytes += gzippedBytes(readFileSync(join(distDir, path)));
}

const mg = totalBytes * G_PER_BYTE * 1000;
const kb = totalBytes / 1024;

const meta = `<meta name="co2-first-load" content="${mg.toFixed(1)}|${kb.toFixed(1)}">`;
if (!html.includes('</head>')) {
  throw new Error(`no </head> in ${indexPath}`);
}
writeFileSync(indexPath, html.replace('</head>', `${meta}</head>`));

console.log(
  `co2-first-load: ${kb.toFixed(1)} KB gzipped (${assetPaths.length + 1} files) → ${(mg / 1000).toFixed(2)} g CO₂`,
);
