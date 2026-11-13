import { activeNav, SETTINGS_ITEMS } from './navigation';

const DEFAULT_TITLE = 'Hacker Tracker';

const STATIC_TITLES: Record<string, string> = {
  ...Object.fromEntries(SETTINGS_ITEMS.map((i) => [i.to, i.label])),
  '/org/assets/upload': 'Upload inventory',
  '/glossary': 'Glossary',
  '/onboarding': 'Set up your organisation',
};

export function titleFor(pathname: string): string {
  const { group, item } = activeNav(pathname);
  if (pathname.startsWith('/invites/')) return 'Organisation invite';
  return STATIC_TITLES[pathname] ?? item?.label ?? group?.label ?? DEFAULT_TITLE;
}
