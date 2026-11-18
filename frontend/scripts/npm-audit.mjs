#!/usr/bin/env node
// `npm audit --audit-level=high` with a dated allowlist: npm audit has no ignore flag.
// Each entry stops working after its expiry, so the audit fails and someone re-checks.
import { spawnSync } from 'node:child_process';

const ALLOW = [
  {
    id: 'GHSA-fc5q-39xc-vjpf',
    expires: '2027-01-31',
    // picomatch ReDoS, no fixed release; build tools only match our own globs.
    reason: 'https://github.com/advisories/GHSA-fc5q-39xc-vjpf',
  },
];
const FAIL_ON = new Set(['high', 'critical']);

// npm audit exits 1 when it finds anything, so judge by the JSON, not the status.
const run = spawnSync('npm', ['audit', '--json'], {
  encoding: 'utf8',
  maxBuffer: 64 << 20,
});
const report = JSON.parse(run.stdout);
if (!report.vulnerabilities) {
  console.error('npm audit returned no report:', run.stdout || run.stderr);
  process.exit(1);
}

const today = new Date().toISOString().slice(0, 10);
const active = new Set();
for (const a of ALLOW) {
  if (today > a.expires)
    console.error(
      `Audit exception for ${a.id} expired on ${a.expires}: re-check ${a.reason}`,
    );
  else active.add(a.id);
}

// Advisory objects only sit on the package that has the flaw; dependents list
// package names. So every chain ends at one of these leaves.
const blocking = new Map();
for (const [name, vuln] of Object.entries(report.vulnerabilities)) {
  for (const via of vuln.via) {
    if (typeof via === 'string' || !FAIL_ON.has(via.severity)) continue;
    const id = via.url.split('/').pop();
    if (active.has(id)) console.log(`allowed: ${name} ${id} (${via.severity})`);
    else blocking.set(`${name} ${id}`, via);
  }
}

for (const [key, via] of blocking)
  console.error(`BLOCKING: ${key} (${via.severity}) ${via.title} ${via.url}`);
if (blocking.size) process.exit(1);
console.log('npm audit: no high or critical advisory outside the allowlist');
