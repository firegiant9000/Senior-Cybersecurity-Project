import { isPlatformAdmin } from '../utils/roleUtils';

export type Requirement = 'org' | 'platformAdmin';

export interface NavItem {
  id: string;
  label: string;
  to: string;
  requires?: Requirement;
}

export interface NavGroup {
  id: 'overview' | 'org' | 'intel' | 'admin';
  label: string;
  to: string;
  requires?: Requirement;
  items: NavItem[];
}

const org = (id: string, label: string, to: string): NavItem => ({
  id,
  label,
  to,
  requires: 'org',
});
const admin = (id: string, label: string, to: string): NavItem => ({
  id,
  label,
  to,
  requires: 'platformAdmin',
});

const ORG_ITEMS: NavItem[] = [
  org('assets', 'Assets', '/org/assets'),
  org('findings', 'Findings', '/org/findings'),
  org('vendorAlerts', 'Vendor Alerts', '/org/vendor-alerts'),
  org('smbAdvisor', 'Risk Profile', '/org/risk'),
  org('aiSummary', 'AI Briefing', '/org/briefing'),
];

const INTEL_ITEMS: NavItem[] = [
  { id: 'vulnerabilities', label: 'Vulnerabilities', to: '/intel/vulnerabilities' },
  { id: 'anomalies', label: 'Anomalies', to: '/intel/anomalies' },
  { id: 'trends', label: 'Incident Trends', to: '/intel/trends' },
  { id: 'dataSources', label: 'Reference Data', to: '/intel/reference' },
];

const ADMIN_ITEMS: NavItem[] = [
  admin('pipelineHealth', 'Pipeline Health', '/admin/pipeline'),
  admin('normalizationLog', 'Normalization Log', '/admin/normalization-log'),
  admin('assessmentDebug', 'Assessment Debug', '/admin/assessment-debug'),
];

export const NAV_GROUPS: NavGroup[] = [
  { id: 'overview', label: 'Overview', to: '/overview', items: [] },
  { id: 'org', label: 'My organisation', to: ORG_ITEMS[0].to, requires: 'org', items: ORG_ITEMS },
  { id: 'intel', label: 'Threat intelligence', to: INTEL_ITEMS[0].to, items: INTEL_ITEMS },
  { id: 'admin', label: 'Admin', to: ADMIN_ITEMS[0].to, requires: 'platformAdmin', items: ADMIN_ITEMS },
];

export const AVATAR_ITEMS: NavItem[] = [
  { id: 'orgProfile', label: 'Organisation profile', to: '/settings/organisation' },
  { id: 'team', label: 'Team and agents', to: '/settings/team' },
  { id: 'integrations', label: 'Integrations', to: '/settings/integrations' },
  { id: 'account', label: 'Account', to: '/settings/account' },
  { id: 'glossary', label: 'Glossary', to: '/glossary' },
  { id: 'privacy', label: 'Privacy', to: '/privacy' },
  { id: 'dataHandling', label: 'Data handling', to: '/data-handling' },
];

export const SETTINGS_ITEMS: NavItem[] = [
  { id: 'account', label: 'Account', to: '/settings/account' },
  { id: 'organisation', label: 'Organisation', to: '/settings/organisation' },
  { id: 'technology', label: 'Technology stack', to: '/settings/technology' },
  { id: 'domains', label: 'Domains', to: '/settings/domains' },
  { id: 'uploads', label: 'File uploads', to: '/settings/uploads' },
  { id: 'team', label: 'Team', to: '/settings/team' },
  { id: 'agents', label: 'Scanner agents', to: '/settings/agents' },
  { id: 'integrations', label: 'Integrations', to: '/settings/integrations' },
];

export function visibleNav(ctx: { role: string | null; orgId: number | null }): NavGroup[] {
  const allowed = (r?: Requirement): boolean => {
    if (r === 'org') return ctx.orgId !== null;
    if (r === 'platformAdmin') return isPlatformAdmin(ctx.role);
    return true;
  };
  return NAV_GROUPS.filter((g) => allowed(g.requires))
    .map((g) => ({ ...g, items: g.items.filter((i) => allowed(i.requires)) }))
    .filter((g) => g.items.length > 0 || NAV_GROUPS.find((n) => n.id === g.id)?.items.length === 0);
}

function pathOf(to: string): string {
  return to.split('?')[0];
}

function matchesPath(pathname: string, p: string): boolean {
  return pathname === p || pathname.startsWith(p + '/');
}

/** Longest path-prefix match (segment-aware) over NAV_GROUPS items; a group with no items matches its own `to`. */
export function activeNav(pathname: string): { group: NavGroup | null; item: NavItem | null } {
  let best: { group: NavGroup; item: NavItem | null } | null = null;
  let bestLen = -1;
  for (const group of NAV_GROUPS) {
    const candidates: { item: NavItem | null; to: string }[] =
      group.items.length === 0
        ? [{ item: null, to: group.to }]
        : group.items.map((item) => ({ item, to: item.to }));
    for (const c of candidates) {
      const p = pathOf(c.to);
      if (matchesPath(pathname, p) && p.length > bestLen) {
        best = { group, item: c.item };
        bestLen = p.length;
      }
    }
  }
  return best ?? { group: null, item: null };
}
