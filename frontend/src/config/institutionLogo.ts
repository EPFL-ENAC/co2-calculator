// Logo shown in the header, the login card and the printed report (#500).
// Kept out of runtime.ts: that module also loads in plain Node (Playwright
// component-test collection), where an SVG import does not resolve.
import epflLogo from '@/assets/epfl-logo.svg';
import { runtimeConfig } from '@/config/runtime';

export const institutionLogo = runtimeConfig.institution.logoUrl || epflLogo;
