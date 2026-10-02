#!/usr/bin/env node
// Prepare what vite-ssr-i18n-basic cannot know about this docs site, before
// `vite`: the section and plan indexes (a port of ../gen_indexes.py, written
// to the same gitignored _index.md files), the sidebar nav from
// ../zensical.toml (src/data/meta.json), routes.config.json, and the page
// images. The plugin renders ../src/**/*.md itself.

import { cpSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import matter from "gray-matter";
import { parse as parseToml } from "smol-toml";

const SRC = "../src";
const INDEX = "_index.md";
const PLANS = "implementation-plans";
const ASSET_RE = /\.(png|jpe?g|gif|svg|webp)$/i;

const project = parseToml(readFileSync("../zensical.toml", "utf8")).project;
const repoUrl = project.repo_url.replace(/\/$/, "");
const siteName = project.site_name;

const files = readdirSync(SRC, { recursive: true }).sort();
const read = (f) => matter(readFileSync(join(SRC, f), "utf8"));

// --- Indexes: same output as ../gen_indexes.py -----------------------------

const STATUS = {
  delivered: "Delivered",
  "in-progress": "In progress",
  abandoned: "Abandoned",
  uncategorized: "Uncategorized",
};

// js-yaml turns `2026-05-05` into a Date; PyYAML's date prints as ISO.
const text = (v) =>
  v instanceof Date ? v.toISOString().slice(0, 10) : String(v);

function titleOf(data, body, fallback) {
  if (data.title) return text(data.title);
  const h1 = body.split("\n").find((line) => line.startsWith("# "));
  return h1 ? h1.slice(2).trim() : fallback;
}

function issueCell(issue) {
  const value = String(issue || "")
    .trim()
    .replace(/^#+/, "");
  const match = value.match(/^\s*#?\s*(\d+)/);
  if (!value || !match) return value;
  return `[#${value}](${repoUrl}/issues/${match[1]})`;
}

function sectionIndex(section) {
  const rows = files
    .filter((f) => dirname(f) === section && f.endsWith(".md"))
    .filter(
      (f) =>
        !["index.md", "index_.md", INDEX].includes(basename(f).toLowerCase()),
    )
    .map((f) => {
      const { data, content } = read(f);
      return `- [${titleOf(data, content, basename(f, ".md"))}](${basename(f)})`;
    });
  const title = section
    .replaceAll("-", " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
  const lines = [
    `# ${title} index`,
    "",
    ...(rows.length ? rows : ["_No pages yet._"]),
  ];
  writeFileSync(join(SRC, section, INDEX), lines.join("\n") + "\n");
}

function plansIndex() {
  const groups = Object.fromEntries(Object.keys(STATUS).map((k) => [k, []]));
  const errors = [];
  const plans = [PLANS, `${PLANS}/archive`].flatMap((dir) =>
    files.filter(
      (f) => dirname(f) === dir && f.endsWith(".md") && basename(f) !== INDEX,
    ),
  );
  for (const f of plans) {
    const { data, content } = read(f);
    let status =
      String(data.status ?? "")
        .trim()
        .toLowerCase() || "uncategorized";
    if (!Object.hasOwn(groups, status)) {
      errors.push(
        `${basename(f)}: unknown plan status '${status}' — use one of delivered, in-progress, abandoned`,
      );
      status = "uncategorized";
    }
    groups[status].push({
      title: titleOf(data, content, basename(f, ".md")),
      issue: data.issue ?? "",
      lastUpdated: text(data.last_updated ?? ""),
      summary: text(data.summary ?? ""),
      filename: f.slice(PLANS.length + 1),
    });
  }
  const total = Object.values(groups).reduce((n, g) => n + g.length, 0);
  const lines = [
    "# Implementation plans",
    "",
    `Plans live in \`docs/src/implementation-plans/\`. ${total} total.`,
    "",
  ];
  for (const [key, entries] of Object.entries(groups)) {
    if (!entries.length) continue;
    lines.push(`## ${STATUS[key]} (${entries.length})`, "");
    lines.push(
      "| Title | Issue | Last updated | Summary |",
      "| --- | --- | --- | --- |",
    );
    for (const e of entries) {
      const summary = e.summary.replaceAll("|", "\\|");
      lines.push(
        `| [${e.title}](${e.filename}) | ${issueCell(e.issue)} | ${e.lastUpdated} | ${summary} |`,
      );
    }
    lines.push("");
  }
  writeFileSync(join(SRC, PLANS, INDEX), lines.join("\n") + "\n");
  return errors;
}

for (const section of ["architecture", "backend", "frontend"])
  sectionIndex(section);
const statusErrors = plansIndex();
if (statusErrors.length) {
  console.error(statusErrors.join("\n"));
  process.exit(1);
}

// --- Nav, routes, images ---------------------------------------------------

// zensical.toml nav → { title, key } leaves and { title, children } sections;
// `keys` lists every page under an entry so the layout can open its section.
function navItems(items) {
  return items.map((item) => {
    const [[title, target]] = Object.entries(item);
    if (Array.isArray(target)) {
      const children = navItems(target);
      return { title, children, keys: children.flatMap((c) => c.keys) };
    }
    const key = target.replace(/\.md$/, "");
    return { title, key, keys: [key] };
  });
}

writeFileSync(
  "src/data/meta.json",
  JSON.stringify({ siteName, repoUrl, nav: navItems(project.nav) }, null, 2) +
    "\n",
);

// One locale, no URL prefix: pages land where MkDocs put them. Every page is
// Markdown, so the plugin derives the routes.
writeFileSync(
  "routes.config.json",
  JSON.stringify(
    { locales: ["en"], basePath: { en: "" }, routes: [] },
    null,
    2,
  ) + "\n",
);

// The plugin only processes src/assets/**; page images keep their paths.
for (const f of files.filter((f) => ASSET_RE.test(f))) {
  cpSync(join(SRC, f), join("dist", f));
}
