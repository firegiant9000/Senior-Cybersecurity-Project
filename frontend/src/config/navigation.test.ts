import { describe, it, expect } from 'vitest';
import { NAV_GROUPS, AVATAR_ITEMS, visibleNav, activeNav } from './navigation';
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
    expect(titleFor('/settings/account')).toBe('Settings');
    expect(titleFor('/settings/technology')).toBe('Organisation profile');
  });
});

describe('AVATAR_ITEMS', () => {
  it('points at the settings paths', () => {
    expect(AVATAR_ITEMS.filter((i) => i.to.startsWith('/settings/')).map((i) => i.to)).toEqual([
      '/settings/organisation',
      '/settings/team',
      '/settings/integrations',
      '/settings/account',
    ]);
  });
});
