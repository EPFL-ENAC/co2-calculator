// Gives `vite preview` (the e2e tests) what nginx serves in the container:
// the institution folder, and the page with the values and the theme inside
// (#3244). The script rewrites dist/spa/index.html in place.
import { join, resolve } from 'node:path';
import { loadEnvLocal, writeInstitutionFiles } from './institution.mjs';

// Only a run by hand reads .env.local (`npm run preview`, `make lighthouse`).
// The tests and CI leave the flag out, so they run on the tracked values.
if (process.argv.includes('--env-local')) loadEnvLocal();
const distDir = resolve(import.meta.dirname, '../dist/spa');
writeInstitutionFiles(distDir, join(distDir, 'index.html'));
console.log(`[institution] prepared ${distDir} for preview`);
