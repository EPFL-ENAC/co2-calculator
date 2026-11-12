// Gives `vite preview` (the e2e tests) the files nginx serves in the
// container: injectEnv.js, theme.css and the institution folder (#3244).
import { resolve } from 'node:path';
import {
  copyInstitutionAssets,
  writeInstitutionFiles,
} from './institution.mjs';

const distDir = resolve(import.meta.dirname, '../dist/spa');
writeInstitutionFiles(distDir);
copyInstitutionAssets(distDir);
console.log(`[institution] prepared ${distDir} for preview`);
