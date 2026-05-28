#!/usr/bin/env node
/**
 * Generate TypeScript types from the FastAPI OpenAPI schema.
 *
 * Strategy (POC, issue #217):
 *   1. Source = live backend at API_URL when reachable (preferred for CI).
 *   2. Fallback = committed snapshot scripts/openapi.snapshot.json
 *      (lets the POC and offline contributors regenerate without docker).
 *
 * Output: src/types/api/openapi.d.ts — committed so IDE support works
 * without re-running the generator.
 */
import { spawnSync } from 'node:child_process';
import { existsSync, mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRONTEND_ROOT = resolve(__dirname, '..');
const SNAPSHOT_PATH = join(__dirname, 'openapi.snapshot.json');
const OUTPUT_PATH = join(FRONTEND_ROOT, 'src/types/api/openapi.d.ts');
const API_URL = process.env.OPENAPI_URL ?? 'http://localhost:8000/openapi.json';
const FETCH_TIMEOUT_MS = 3000;

async function tryFetchLive() {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const res = await fetch(API_URL, { signal: controller.signal });
    if (!res.ok) {
      console.warn(
        `[gen-api-types] live fetch HTTP ${res.status}, falling back to snapshot`,
      );
      return null;
    }
    return await res.text();
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    console.warn(
      `[gen-api-types] live fetch failed (${reason}), falling back to snapshot`,
    );
    return null;
  } finally {
    clearTimeout(timer);
  }
}

async function main() {
  let schemaText = await tryFetchLive();
  let usedSource;

  if (schemaText) {
    usedSource = `live ${API_URL}`;
  } else {
    if (!existsSync(SNAPSHOT_PATH)) {
      console.error(
        `[gen-api-types] no live backend and no snapshot at ${SNAPSHOT_PATH}`,
      );
      process.exit(1);
    }
    usedSource = `snapshot ${SNAPSHOT_PATH}`;
  }

  // openapi-typescript reads from a file path or URL. Stage live JSON in a
  // tmpfile so the tool sees a stable on-disk input either way.
  const stagingDir = mkdtempSync(join(tmpdir(), 'openapi-ts-'));
  const stagedInput = join(stagingDir, 'openapi.json');
  try {
    if (schemaText) {
      writeFileSync(stagedInput, schemaText);
    }
    const inputPath = schemaText ? stagedInput : SNAPSHOT_PATH;
    console.log(`[gen-api-types] generating from ${usedSource}`);
    const result = spawnSync(
      'npx',
      ['openapi-typescript', inputPath, '-o', OUTPUT_PATH],
      { cwd: FRONTEND_ROOT, stdio: 'inherit' },
    );
    if (result.status !== 0) {
      process.exit(result.status ?? 1);
    }
    console.log(`[gen-api-types] wrote ${OUTPUT_PATH}`);
  } finally {
    rmSync(stagingDir, { recursive: true, force: true });
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
