# Eco-design
Monitored throughout the project using the [Green IT best practices](https://rweb.greenit.fr/en). We selected the most relevant practices and their associated impact levels for this project; below is a summary of the actions we apply:

## Front-End
- Minimize resource usage: reduce animations, CSS files and HTTP requests; externalize and minify CSS/JS; keep page weight under 1 MB.
- Efficient loading: lazy-load SPA routes; memory-cache frequently used data; avoid redundant API calls.
- Optimized visuals: prefer CSS over images; use SVG/glyphs; optimize images before integration; no client-side raster resizing.
- Performance practices: minimize reflows; avoid blocking JS; run Lighthouse checks.

### Back-End
- Reduce data volume: return only essential fields; cache selected data; minimize payload size.
- Favor simplicity: use a custom backend; no CMS layer.

## Implementation
- Efficient codebase (Implementation): enforce linters; externalize, minify and combine CSS/JS; let build tooling optimize bundles.
- Optimized DOM operations: reduce DOM updates via Vue component structure; avoid redundant traversals.
- Efficient CSS: use logical structure, optimized selectors and @layer; reduce selector complexity.
- Smart loading: load data and code on demand; cache JS objects when useful.
- Browser features: enable native lazy loading; no Service Worker.

## Optimisations
- Caching strategy: serve static assets via CDN with cache-control headers; avoid app-level caching or CMS caching when possible.
- Compression & minification: minify and compress all text and static assets; minimize HTTP requests.
- Clean infrastructure: avoid unnecessary overrides; keep sitemaps current; apply data expiration policies.

## Environmental Metrics
These metrics are tracked with [Green IT tools](https://github.com/cnumr), as the plugin for [Lighthouse](https://github.com/cnumr/lighthouse-plugin-ecoindex#readme):

- Energy efficiency: track energy usage.
- Carbon footprint: estimate carbon impact.