#!/usr/bin/env node
// Convert ../src/**/*.md into src/pages/**/*.eta so vite-ssr-i18n-basic can
// render them, after pierreguilbert.com's build-blog.mjs. It also does what
// the Python side does for MkDocs and Zensical: the section and plan indexes
// (a port of ../gen_indexes.py, written to the same gitignored _index.md
// files), the sidebar nav from ../zensical.toml, and routes.config.json.

import {
  cpSync,
  mkdirSync,
  readFileSync,
  readdirSync,
  rmSync,
  writeFileSync,
} from "node:fs";
import { basename, dirname, join } from "node:path";
import matter from "gray-matter";
import { Marked } from "marked";
import { parse as parseToml } from "smol-toml";

const SRC = "../src";
const PAGES = "src/pages";
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

// --- Markdown → HTML --------------------------------------------------------

const escapeHtml = (s) =>
  s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");

const plainText = (html) =>
  html
    .replace(/<[^>]+>/g, "")
    .replaceAll("&lt;", "<")
    .replaceAll("&gt;", ">")
    .replaceAll("&quot;", '"')
    .replaceAll("&#39;", "'")
    .replaceAll("&amp;", "&");

// Python-Markdown's toc slugify + unique(), so cross-page #anchors keep working.
const slugify = (s) =>
  s
    .normalize("NFKD")
    .replace(/[^\x00-\x7f]/g, "")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, "-");

function uniqueId(id, ids) {
  while (ids.has(id) || !id) {
    const m = id.match(/^(.*)_([0-9]+)$/);
    id = m ? `${m[1]}_${Number(m[2]) + 1}` : `${id}_1`;
  }
  ids.add(id);
  return id;
}

// Per-page state the renderer hooks read; reset before each page.
let ids = new Set();
let hasMermaid = false;

const marked = new Marked({ gfm: true });
marked.use({
  renderer: {
    heading({ tokens, depth }) {
      const inner = this.parser.parseInline(tokens);
      const id = uniqueId(slugify(plainText(inner)), ids);
      return `<h${depth} id="${id}">${inner}<a class="headerlink" href="#${id}">¶</a></h${depth}>\n`;
    },
    code({ text: code, lang }) {
      if (lang !== "mermaid") return false;
      hasMermaid = true;
      return `<pre class="mermaid">${escapeHtml(code)}</pre>\n`;
    },
  },
  walkTokens(token) {
    if (token.type !== "link" || /^(https?:|mailto:|#)/.test(token.href))
      return;
    token.href = token.href.replace(/\.md(#|$)/, ".html$1");
  },
});

// --- Nav --------------------------------------------------------------------

function navHtml(items, current, root) {
  const lis = items.map((item) => {
    const [[title, target]] = Object.entries(item);
    if (Array.isArray(target)) {
      const inner = navHtml(target, current, root);
      const open = inner.includes('aria-current="page"') ? " open" : "";
      return `<li><details${open}><summary>${escapeHtml(title)}</summary>${inner}</details></li>`;
    }
    const here = target === current ? ' aria-current="page"' : "";
    const href = root + target.replace(/\.md$/, ".html");
    return `<li><a href="${href}"${here}>${escapeHtml(title)}</a></li>`;
  });
  return `<ul>${lis.join("")}</ul>`;
}

// --- Pages, routes, assets --------------------------------------------------

rmSync(PAGES, { recursive: true, force: true });
const routes = [];
const pages = readdirSync(SRC, { recursive: true }).filter((f) =>
  f.endsWith(".md"),
);

for (const f of pages) {
  const { data, content } = read(f);
  const key = f.replace(/\.md$/, "");
  const title = titleOf(data, content, basename(key));
  const root = "../".repeat(key.split("/").length - 1);
  ids = new Set();
  hasMermaid = false;
  // A literal `<%` in a page would open an Eta tag; `&lt;%` renders the same.
  const html = marked.parse(content).replaceAll("<%", "&lt;%");
  const layoutData = JSON.stringify({
    title,
    root,
    mermaid: hasMermaid,
    siteName,
    repoUrl,
  });
  const eta = [
    `<% layout('/layouts/main', ${layoutData}) %>`,
    `<nav class="sidebar">${navHtml(project.nav, f, root)}</nav>`,
    `<main><article class="md">\n${html}\n</article></main>`,
    "",
  ].join("\n");
  mkdirSync(join(PAGES, dirname(f)), { recursive: true });
  writeFileSync(join(PAGES, `${key}.eta`), eta);
  routes.push({ key, path: `/${key}.html`, title, hidden: true });
}

// One locale under /docs: the plugin always writes a root index.html
// language redirect, so the docs home cannot sit at the site root.
writeFileSync(
  "routes.config.json",
  JSON.stringify(
    { locales: ["en"], basePath: { en: "/docs" }, routes },
    null,
    2,
  ) + "\n",
);

// The plugin only processes src/assets/**; page images keep their paths.
for (const f of files.filter((f) => ASSET_RE.test(f))) {
  cpSync(join(SRC, f), join("dist/docs", f));
}

console.log(`build-pages: ${pages.length} pages, ${routes.length} routes`);
