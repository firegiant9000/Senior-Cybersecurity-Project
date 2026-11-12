import { TAB_GROUPS, LEGACY_TAB_MAP } from './tabGroups';

const DEFAULT_TITLE = 'Hacker Tracker';

const STATIC_TITLES: Record<string, string> = {
  '/settings': 'Settings',
  '/settings/assessment-debug': 'Assessment Debug',
  '/org-profile': 'Organisation profile',
  '/glossary': 'Glossary',
  '/assets': 'Upload inventory',
  '/inventory/upload': 'Upload inventory',
  '/integrations': 'Integrations',
  '/onboarding': 'Set up your organisation',
};

function dashboardTitle(search: string): string {
  const params = new URLSearchParams(search);
  const rawTab = params.get('tab');
  const rawSub = params.get('sub');

  const legacy = rawTab ? LEGACY_TAB_MAP[rawTab] : undefined;
  const tabId = legacy?.sub ? legacy.tab : (rawTab ?? 'overview');
  const subId = legacy?.sub ? legacy.sub : rawSub;

  // Dashboard renders Overview for an unknown tab, so the title follows.
  const group = TAB_GROUPS.find((g) => g.id === tabId) ?? TAB_GROUPS[0];
  if (group.subTabs) {
    const sub = group.subTabs.find((s) => s.id === subId) ?? group.subTabs[0];
    return sub.label;
  }
  return group.label;
}

export function titleFor(pathname: string, search: string): string {
  if (pathname === '/dashboard') return dashboardTitle(search);
  if (pathname.startsWith('/invites/')) return 'Organisation invite';
  return STATIC_TITLES[pathname] ?? DEFAULT_TITLE;
}
