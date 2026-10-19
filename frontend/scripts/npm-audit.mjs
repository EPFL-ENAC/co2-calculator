// `npm audit --audit-level=high`, minus advisories we accepted on purpose.
//
// npm has no ignore list, so a single unpatchable advisory in dev tooling
// keeps the audit red forever and teaches everyone to stop reading it. Each
// accepted advisory stops applying as soon as a fix ships or it goes away.
import { spawnSync } from 'node:child_process';

const ACCEPTED = new Set([
  // braces <=3.0.3 stack-exhaustion DoS, no patched release (2026-10). Reached
  // only via dev tooling (stylelint, eslint config, vue-i18n plugin ->
  // fast-glob -> micromatch) expanding globs from our own config. Runtime
  // deps are audited with no exceptions by `make audit`.
  'https://github.com/advisories/GHSA-vfj7-8cjw-p6xm',
]);

const { stdout } = spawnSync('npm', ['audit', '--json'], { encoding: 'utf8' });
const report = JSON.parse(stdout);
if (!report?.vulnerabilities) throw new Error(`npm audit failed: ${stdout}`);

// Every `via` chain ends at an advisory object; strings only point along it.
const advisories = new Map(
  Object.values(report.vulnerabilities).flatMap((vuln) =>
    vuln.via
      .filter(
        (via) =>
          typeof via === 'object' &&
          ['high', 'critical'].includes(via.severity),
      )
      .map((via) => [via.url, via]),
  ),
);

const failures = [];
for (const [url, advisory] of advisories) {
  if (!ACCEPTED.has(url))
    failures.push(`${advisory.name}: ${advisory.title} (${url})`);
  else if (report.vulnerabilities[advisory.name].fixAvailable !== false)
    failures.push(
      `${advisory.name}: fix available for ${url}, run npm audit fix and drop it from ACCEPTED`,
    );
  else console.log(`accepted: ${advisory.name} ${url}`);
}
for (const url of ACCEPTED) {
  if (!advisories.has(url))
    failures.push(`${url} is no longer reported, drop it from ACCEPTED`);
}

if (failures.length) {
  console.error(
    `npm audit: ${failures.length} high/critical advisories\n${failures.join('\n')}`,
  );
  process.exit(1);
}
console.log('npm audit: no high/critical advisories left');
