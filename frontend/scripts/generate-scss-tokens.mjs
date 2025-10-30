#!/usr/bin/env node
/* eslint-env node */

import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const projectRoot = path.resolve(__dirname, '..');

const TOKENS_FILE = path.join(projectRoot, 'src/css/tokens.css');
const OPTIONS_FILE = path.join(projectRoot, 'src/css/02-tokens/_options.scss');
const DECISIONS_FILE = path.join(
  projectRoot,
  'src/css/02-tokens/_decisions.scss',
);

const OPTION_PREFIXES = ['---tokens-', '--_tokens-', '--tokens-'];

function classify(cssName) {
  return OPTION_PREFIXES.some((prefix) => cssName.startsWith(prefix))
    ? 'option'
    : 'decision';
}

function toScssVariable(cssName) {
  let name = cssName.replace(/^--+/, '');
  name = name.replace(/^_+/, '');
  name = name.replace(/_/g, '-');
  // collapse multiple consecutive dashes introduced by cleanup
  name = name.replace(/-{2,}/g, '-');
  return `$${name}`;
}

function replaceVars(rawValue, records, stage) {
  return rawValue.replace(/var\(\s*(--[\w-]+)\s*\)/g, (_, matchName) => {
    const reference = records.get(matchName);
    if (!reference) {
      globalThis.console.warn(
        `⚠️  Unknown reference ${matchName} in value ${rawValue}`,
      );
      return `var(${matchName})`;
    }

    if (stage === 'options') {
      return reference.scssName;
    }

    if (reference.classification === 'option') {
      return `opt.${reference.scssName}`;
    }

    return reference.scssName;
  });
}

async function run() {
  const cssContent = await fs.readFile(TOKENS_FILE, 'utf8');
  const varRegex = /(--[\w-]+)\s*:\s*([^;]+);/g;

  const orderedRecords = [];
  const recordMap = new Map();

  let match;
  while ((match = varRegex.exec(cssContent)) !== null) {
    const cssName = match[1];
    const rawValue = match[2].trim();
    const classification = classify(cssName);
    const scssName = toScssVariable(cssName);

    const record = {
      cssName,
      scssName,
      classification,
      rawValue,
    };

    orderedRecords.push(record);
    recordMap.set(cssName, record);
  }

  const options = orderedRecords.filter(
    (record) => record.classification === 'option',
  );
  const decisions = orderedRecords.filter(
    (record) => record.classification === 'decision',
  );

  const optionsLines = options.map((record) => {
    const value = replaceVars(record.rawValue, recordMap, 'options');
    return `${record.scssName}: ${value} !default;`;
  });

  const optionsHeader = `// -----------------------------------------------------------------------------\n// ⚠️  Auto-generated file\n// -----------------------------------------------------------------------------\n// Generated from src/css/tokens.css via scripts/generate-scss-tokens.mjs\n// Do not edit manually.\n\n`;

  await fs.writeFile(
    OPTIONS_FILE,
    optionsHeader + optionsLines.join('\n') + '\n',
  );

  const decisionsLines = decisions.map((record) => {
    const value = replaceVars(record.rawValue, recordMap, 'decisions');
    return `${record.scssName}: ${value} !default;`;
  });

  const decisionsHeader = `// -----------------------------------------------------------------------------\n// ⚠️  Auto-generated file\n// -----------------------------------------------------------------------------\n// Generated from src/css/tokens.css via scripts/generate-scss-tokens.mjs\n// Do not edit manually.\n\n@use 'options' as opt;\n\n`;

  await fs.writeFile(
    DECISIONS_FILE,
    decisionsHeader + decisionsLines.join('\n') + '\n',
  );

  globalThis.console.log(`✓ Generated ${OPTIONS_FILE}`);
  globalThis.console.log(`✓ Generated ${DECISIONS_FILE}`);
}

run().catch((error) => {
  globalThis.console.error('Failed to generate Sass tokens:', error);
  globalThis.process.exit(1);
});
