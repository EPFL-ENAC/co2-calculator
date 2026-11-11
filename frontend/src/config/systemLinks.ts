// Operations links of the system logs page (#500): GitOps, monitoring, logs
// and platform consoles per environment. They name the infrastructure of the
// institution, so they come from APP_SYSTEM_LINKS, a JSON array:
//   [{"name":"dev","gitops":[{"label":"GitOps","url":"https://..."}],
//     "monitoring":[],"appLogs":[],"platform":[]}]
// Empty means no links. A value that does not parse stops the startup
// (src/config/requiredConfig.ts).
import { runtimeConfig } from '@/config/runtime';

export interface SystemLink {
  label: string;
  url: string;
}

export interface SystemEnvironmentLinks {
  name: string;
  gitops: SystemLink[];
  monitoring: SystemLink[];
  appLogs: SystemLink[];
  platform: SystemLink[];
}

const GROUPS = ['gitops', 'monitoring', 'appLogs', 'platform'] as const;

function isLinkList(value: unknown): value is SystemLink[] {
  return (
    Array.isArray(value) &&
    value.every(
      (link) =>
        typeof link?.label === 'string' && typeof link?.url === 'string',
    )
  );
}

export function parseSystemLinks(raw: string): SystemEnvironmentLinks[] {
  if (raw === '') return [];
  const parsed: unknown = JSON.parse(raw);
  const valid =
    Array.isArray(parsed) &&
    parsed.every(
      (env) =>
        typeof env?.name === 'string' &&
        GROUPS.every((group) => isLinkList(env[group])),
    );
  if (!valid) {
    throw new Error(
      'APP_SYSTEM_LINKS must be a JSON array of {name, gitops, monitoring, appLogs, platform}',
    );
  }
  return parsed as SystemEnvironmentLinks[];
}

export function systemLinks(): SystemEnvironmentLinks[] {
  return parseSystemLinks(runtimeConfig.systemLinks);
}
