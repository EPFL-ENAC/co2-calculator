// Gives `vite preview` (the e2e tests) the files nginx serves in the
// container: injectEnv.js, theme.css and the institution folder (#3244).
import { resolve } from 'node:path';
import { loadEnvLocal, writeInstitutionFiles } from './institution.mjs';

// Only a run by hand reads .env.local (`npm run preview`, `make lighthouse`).
// The tests and CI leave the flag out, so they run on the tracked values.
if (process.argv.includes('--env-local')) loadEnvLocal();
const distDir = resolve(import.meta.dirname, '../dist/spa');
writeInstitutionFiles(distDir);
console.log(`[institution] prepared ${distDir} for preview`);
