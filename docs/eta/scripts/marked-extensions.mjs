// marked extensions for parity with the MkDocs/Zensical build: Python-
// Markdown heading ids, so existing `page.md#anchor` links keep working,
// and Mermaid diagrams.

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

// Python-Markdown's toc slugify + unique().
const slugify = (s) =>
  s
    .normalize("NFKD")
    .replace(/[^\x00-\x7f]/g, "")
    .replace(/[^\w\s-]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, "-");

const ids = new Set(); // ids used on the page being rendered

function uniqueId(id) {
  while (ids.has(id) || !id) {
    const m = id.match(/^(.*)_([0-9]+)$/);
    id = m ? `${m[1]}_${Number(m[2]) + 1}` : `${id}_1`;
  }
  ids.add(id);
  return id;
}

export const pythonMarkdownIds = {
  hooks: {
    preprocess(markdown) {
      ids.clear();
      return markdown;
    },
  },
  renderer: {
    heading({ tokens, depth }) {
      const inner = this.parser.parseInline(tokens);
      const id = uniqueId(slugify(plainText(inner)));
      return `<h${depth} id="${id}">${inner}<a class="headerlink" href="#${id}">¶</a></h${depth}>\n`;
    },
  },
};

export const mermaid = {
  renderer: {
    code({ text, lang }) {
      if (lang !== "mermaid") return false;
      return `<pre class="mermaid">${escapeHtml(text)}</pre>\n`;
    },
  },
};
