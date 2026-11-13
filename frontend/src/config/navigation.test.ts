import { describe, it, expect } from 'vitest';
import { NAV_GROUPS, AVATAR_ITEMS, SETTINGS_ITEMS, visibleNav, activeNav } from './navigation';
import { titleFor } from './pageTitles';

describe('NAV_GROUPS', () => {
  it('lists groups in order', () => {
    expect(NAV_GROUPS.map((g) => g.label)).toEqual([
      'Overview',
      'My organisation',
      'Threat intelligence',
      'Admin',
    ]);
  });

  it('lists My organisation items in order', () => {
    const org = NAV_GROUPS.find((g) => g.id === 'org')!;
    expect(org.items.map((i) => i.label)).toEqual([
      'Assets',
      'Findings',
      'Vendor Alerts',
      'Risk Profile',
      'AI Briefing',
    ]);
  });

  const pairs = (id: string) =>
    NAV_GROUPS.find((g) => g.id === id)!.items.map((i) => ({ label: i.label, to: i.to }));

  it('pins org item targets', () => {
    expect(pairs('org')).toEqual([
      { label: 'Assets', to: '/org/assets' },
      { label: 'Findings', to: '/org/findings' },
      { label: 'Vendor Alerts', to: '/org/vendor-alerts' },
      { label: 'Risk Profile', to: '/org/risk' },
      { label: 'AI Briefing', to: '/org/briefing' },
    ]);
  });

  it('pins merged intel items and drops the old labels', () => {
    expect(pairs('intel')).toEqual([
      { label: 'Vulnerabilities', to: '/intel/vulnerabilities' },
      { label: 'Anomalies', to: '/intel/anomalies' },
      { label: 'Incident Trends', to: '/intel/trends' },
      { label: 'Reference Data', to: '/intel/reference' },
    ]);
    const labels = pairs('intel').map((i) => i.label);
    expect(labels).not.toContain('Recent Vulnerabilities');
    expect(labels).not.toContain('Vulnerability Scoring');
  });

  it('pins admin item targets', () => {
    expect(pairs('admin')).toEqual([
      { label: 'Pipeline Health', to: '/admin/pipeline' },
      { label: 'Normalization Log', to: '/admin/normalization-log' },
      { label: 'Assessment Debug', to: '/admin/assessment-debug' },
    ]);
  });

  it('pins group targets', () => {
    expect(NAV_GROUPS.map((g) => ({ id: g.id, to: g.to }))).toEqual([
      { id: 'overview', to: '/overview' },
      { id: 'org', to: '/org/assets' },
      { id: 'intel', to: '/intel/vulnerabilities' },
      { id: 'admin', to: '/admin/pipeline' },
    ]);
  });
});

describe('visibleNav', () => {
  it('hides admin for non-admins and shows it for admins', () => {
    expect(visibleNav({ role: null, orgId: 1 }).map((g) => g.id)).not.toContain('admin');
    expect(visibleNav({ role: 'admin', orgId: 1 }).map((g) => g.id)).toContain('admin');
  });

  it('hides My organisation without an org but keeps Overview', () => {
    const ids = visibleNav({ role: null, orgId: null }).map((g) => g.id);
    expect(ids).toEqual(['overview', 'intel']);
  });
});

describe('activeNav', () => {
  it('resolves an item by its path', () => {
    expect(activeNav('/org/findings').item?.label).toBe('Findings');
    expect(activeNav('/org/findings').group?.id).toBe('org');
  });

  it('resolves the merged Vulnerabilities item and the other intel items', () => {
    expect(activeNav('/intel/vulnerabilities').item?.label).toBe('Vulnerabilities');
    expect(activeNav('/intel/vulnerabilities').group?.id).toBe('intel');
    expect(activeNav('/intel/anomalies/ic3').item?.label).toBe('Anomalies');
    expect(activeNav('/intel/reference/ic3').item?.label).toBe('Reference Data');
  });

  it('matches by longest segment-aware prefix', () => {
    expect(activeNav('/org/assets/upload').group?.id).toBe('org');
    expect(activeNav('/org/assets/upload').item?.label).toBe('Assets');
    expect(activeNav('/admin/assessment-debug').group?.id).toBe('admin');
    expect(activeNav('/org/assets-x')).toEqual({ group: null, item: null });
  });

  it('resolves Overview to its group with no item', () => {
    expect(activeNav('/overview')).toMatchObject({ item: null });
    expect(activeNav('/overview').group?.id).toBe('overview');
  });

  it('matches nothing for pages outside the nav', () => {
    expect(activeNav('/glossary')).toEqual({ group: null, item: null });
  });
});

describe('titleFor with navigation labels', () => {
  it('uses nav labels on the new paths', () => {
    expect(titleFor('/org/vendor-alerts')).toBe('Vendor Alerts');
    expect(titleFor('/org/risk')).toBe('Risk Profile');
    expect(titleFor('/intel/vulnerabilities')).toBe('Vulnerabilities');
  });

  it('keeps static titles first for other paths', () => {
    expect(titleFor('/org/assets/upload')).toBe('Upload inventory');
    expect(titleFor('/settings/account')).toBe('Account');
    expect(titleFor('/settings/technology')).toBe('Technology stack');
    expect(titleFor('/settings/integrations')).toBe('Integrations');
  });
});

describe('SETTINGS_ITEMS', () => {
  it('pins every settings item label and target in order', () => {
    expect(SETTINGS_ITEMS.map((i) => ({ label: i.label, to: i.to }))).toEqual([
      { label: 'Account', to: '/settings/account' },
      { label: 'Organisation', to: '/settings/organisation' },
      { label: 'Technology stack', to: '/settings/technology' },
      { label: 'Domains', to: '/settings/domains' },
      { label: 'File uploads', to: '/settings/uploads' },
      { label: 'Team', to: '/settings/team' },
      { label: 'Scanner agents', to: '/settings/agents' },
      { label: 'Integrations', to: '/settings/integrations' },
    ]);
  });
});

describe('AVATAR_ITEMS', () => {
  it('pins every avatar item label and target', () => {
    expect(AVATAR_ITEMS.map((i) => ({ label: i.label, to: i.to }))).toEqual([
      { label: 'Organisation profile', to: '/settings/organisation' },
      { label: 'Team and agents', to: '/settings/team' },
      { label: 'Integrations', to: '/settings/integrations' },
      { label: 'Account', to: '/settings/account' },
      { label: 'Glossary', to: '/glossary' },
      { label: 'Privacy', to: '/privacy' },
      { label: 'Data handling', to: '/data-handling' },
    ]);
  });

  it('points at the settings paths', () => {
    expect(AVATAR_ITEMS.filter((i) => i.to.startsWith('/settings/')).map((i) => i.to)).toEqual([
      '/settings/organisation',
      '/settings/team',
      '/settings/integrations',
      '/settings/account',
    ]);
  });
});
