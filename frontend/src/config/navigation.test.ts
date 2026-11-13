import { describe, it, expect } from 'vitest';
import { NAV_GROUPS, visibleNav, activeNav } from './navigation';
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
  it('resolves a legacy flat id', () => {
    expect(activeNav('/dashboard', '?tab=findings').item?.label).toBe('Findings');
  });

  it('defaults to the first sub-tab of a group', () => {
    expect(activeNav('/dashboard', '?tab=assessment').item?.label).toBe('Risk Profile');
    expect(activeNav('/dashboard', '?tab=threats').item?.label).toBe('Recent Vulnerabilities');
    expect(activeNav('/dashboard', '?tab=admin').item?.label).toBe('Pipeline Health');
    expect(activeNav('/dashboard', '?tab=assessment&sub=nope').item?.label).toBe('Risk Profile');
  });

  it('falls back to Overview for an unknown or missing tab', () => {
    expect(activeNav('/dashboard', '?tab=nope')).toMatchObject({ item: null });
    expect(activeNav('/dashboard', '?tab=nope').group?.id).toBe('overview');
    expect(activeNav('/dashboard', '').group?.id).toBe('overview');
  });

  it('matches non-dashboard paths', () => {
    expect(activeNav('/settings/assessment-debug', '').group?.id).toBe('admin');
    expect(activeNav('/inventory/upload', '').group?.id).toBe('org');
    expect(activeNav('/inventory/upload', '').item?.label).toBe('Assets');
    expect(activeNav('/glossary', '')).toEqual({ group: null, item: null });
  });
});

describe('titleFor with navigation labels', () => {
  it('uses nav labels on the dashboard', () => {
    expect(titleFor('/dashboard', '?tab=vendorAlerts')).toBe('Vendor Alerts');
    expect(titleFor('/dashboard', '?tab=assessment')).toBe('Risk Profile');
  });

  it('keeps static titles first for other paths', () => {
    expect(titleFor('/inventory/upload', '')).toBe('Upload inventory');
    expect(titleFor('/settings', '')).toBe('Settings');
  });
});
