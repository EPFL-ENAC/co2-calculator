import { SHIPPED_TEMPLATES } from '@/constant/templateMapping';

// Templates are Vite assets so a replaced file gets a new URL and never sits
// stale in a browser cache. `url` because .csv is not a Vite asset type,
// `no-inline` so files under 4 KB stay files rather than data URIs.
// Browser-only on purpose: templateMapping.ts stays importable from Node tests.
const byPath = import.meta.glob<string>('../assets/templates/*.csv', {
  query: '?url&no-inline',
  import: 'default',
  eager: true,
});

const TEMPLATE_URLS: Record<string, string> = Object.fromEntries(
  Object.entries(byPath).map(([path, url]) => [
    path.slice(path.lastIndexOf('/') + 1),
    url,
  ]),
);

// A wrong glob path matches nothing without a build warning. Fail at boot,
// not on a user's click.
for (const fileName of SHIPPED_TEMPLATES) {
  if (!(fileName in TEMPLATE_URLS)) {
    throw new Error(`Template ${fileName} is mapped but not bundled`);
  }
}

export function getTemplateUrl(fileName: string): string {
  const url = TEMPLATE_URLS[fileName];
  if (!url) throw new Error(`No template asset for ${fileName}`);
  return url;
}
