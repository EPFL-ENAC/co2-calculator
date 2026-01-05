// Import all icons as raw SVG strings
const moduleIcons = import.meta.glob('/src/assets/icons/modules/*.svg', {
  query: '?raw',
  import: 'default',
  eager: true,
});

// Normalize keys to usable names
const normalize = (path: string) => path.split('/').pop()!.replace('.svg', '');

export const icons = Object.fromEntries(
  Object.entries(moduleIcons).map(([path, svg]) => [
    normalize(path),
    svg as string,
  ]),
);
