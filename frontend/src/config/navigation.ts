import { TAB_GROUPS, LEGACY_TAB_MAP } from './tabGroups';
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
  org('assets', 'Assets', '/dashboard?tab=assets'),
  org('findings', 'Findings', '/dashboard?tab=assessment&sub=findings'),
  org('vendorAlerts', 'Vendor Alerts', '/dashboard?tab=vendorAlerts'),
  org('smbAdvisor', 'Risk Profile', '/dashboard?tab=assessment&sub=smbAdvisor'),
  org('aiSummary', 'AI Briefing', '/dashboard?tab=assessment&sub=aiSummary'),
];

const INTEL_ITEMS: NavItem[] = [
  { id: 'threatIntel', label: 'Recent Vulnerabilities', to: '/dashboard?tab=threats&sub=threatIntel' },
  { id: 'riskScoring', label: 'Vulnerability Scoring', to: '/dashboard?tab=threats&sub=riskScoring' },
  { id: 'anomalies', label: 'Anomalies', to: '/dashboard?tab=threats&sub=anomalies' },
  { id: 'trends', label: 'Incident Trends', to: '/dashboard?tab=trendsData&sub=trends' },
  { id: 'dataSources', label: 'Reference Data', to: '/dashboard?tab=trendsData&sub=dataSources' },
];

const ADMIN_ITEMS: NavItem[] = [
  admin('pipelineHealth', 'Pipeline Health', '/dashboard?tab=admin&sub=pipelineHealth'),
  admin('normalizationLog', 'Normalization Log', '/dashboard?tab=admin&sub=normalizationLog'),
  admin('assessmentDebug', 'Assessment Debug', '/settings/assessment-debug'),
];

export const NAV_GROUPS: NavGroup[] = [
  { id: 'overview', label: 'Overview', to: '/dashboard', items: [] },
  { id: 'org', label: 'My organisation', to: ORG_ITEMS[0].to, requires: 'org', items: ORG_ITEMS },
  { id: 'intel', label: 'Threat intelligence', to: INTEL_ITEMS[0].to, items: INTEL_ITEMS },
  { id: 'admin', label: 'Admin', to: ADMIN_ITEMS[0].to, requires: 'platformAdmin', items: ADMIN_ITEMS },
];

export const AVATAR_ITEMS: NavItem[] = [
  { id: 'orgProfile', label: 'Organisation profile', to: '/org-profile' },
  { id: 'team', label: 'Team and agents', to: '/settings' },
  { id: 'integrations', label: 'Integrations', to: '/integrations' },
  { id: 'account', label: 'Account', to: '/settings' },
  { id: 'glossary', label: 'Glossary', to: '/glossary' },
  { id: 'privacy', label: 'Privacy', to: '/privacy' },
  { id: 'dataHandling', label: 'Data handling', to: '/data-handling' },
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

function parseTo(to: string): { path: string; tab: string | null; sub: string | null } {
  const [path, query = ''] = to.split('?');
  const params = new URLSearchParams(query);
  return { path, tab: params.get('tab'), sub: params.get('sub') };
}

const NONE = { group: null, item: null };

export function activeNav(
  pathname: string,
  search: string,
): { group: NavGroup | null; item: NavItem | null } {
  let tab: string | null = null;
  let sub: string | null = null;

  if (pathname === '/dashboard') {
    const params = new URLSearchParams(search);
    const rawTab = params.get('tab');
    const rawSub = params.get('sub');
    const legacy = rawTab ? LEGACY_TAB_MAP[rawTab] : undefined;
    tab = legacy?.sub ? legacy.tab : rawTab;
    sub = legacy?.sub ? legacy.sub : rawSub;

    // Dashboard renders Overview for an unknown tab.
    const def = TAB_GROUPS.find((g) => g.id === tab);
    if (!def || def.id === 'overview') {
      return { group: NAV_GROUPS[0], item: null };
    }
    if (def.subTabs) {
      sub = def.subTabs.find((s) => s.id === sub)?.id ?? def.subTabs[0].id;
    } else {
      sub = null;
    }
  } else if (pathname === '/inventory/upload') {
    tab = 'assets';
  } else {
    for (const group of NAV_GROUPS) {
      const item = group.items.find((i) => parseTo(i.to).path === pathname);
      if (item) return { group, item };
    }
    return NONE;
  }

  for (const group of NAV_GROUPS) {
    const item = group.items.find((i) => {
      const p = parseTo(i.to);
      return p.path === '/dashboard' && p.tab === tab && p.sub === sub;
    });
    if (item) return { group, item };
  }
  return NONE;
}
