import { activeNav } from './navigation';

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

export function titleFor(pathname: string, search: string): string {
  const { group, item } = activeNav(pathname, search);
  if (pathname === '/dashboard') return item?.label ?? group?.label ?? DEFAULT_TITLE;
  if (pathname.startsWith('/invites/')) return 'Organisation invite';
  return STATIC_TITLES[pathname] ?? item?.label ?? group?.label ?? DEFAULT_TITLE;
}
