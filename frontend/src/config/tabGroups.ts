export interface SubTabDef {
  id: string;
  label: string;
  requiresOrg?: boolean;
  requiresAdmin?: boolean;
}

export interface TabGroupDef {
  id: string;
  label: string;
  requiresOrg?: boolean;
  requiresAdmin?: boolean;
  subTabs?: SubTabDef[];
}

/**
 * Flat tab-ID → component key stays unchanged; the group config just
 * controls how they're presented in the navigation chrome.
 *
 * Groups without `subTabs` are standalone — clicking the group directly
 * activates its `id` as the active tab key.
 */
export const TAB_GROUPS: TabGroupDef[] = [
  {
    id: 'overview',
    label: 'Overview',
  },
  {
    id: 'assessment',
    label: 'Assessment',
    requiresOrg: true,
    subTabs: [
      { id: 'smbAdvisor', label: 'SMB Risk Advisor' },
      { id: 'findings', label: 'Findings' },
      { id: 'aiSummary', label: 'AI Summary' },
    ],
  },
  {
    id: 'threats',
    label: 'Threats',
    subTabs: [
      { id: 'threatIntel', label: 'Threat Intelligence' },
      { id: 'riskScoring', label: 'Risk Scoring' },
      { id: 'anomalies', label: 'Anomalies' },
    ],
  },
  {
    id: 'vendorAlerts',
    label: 'Vendors',
    requiresOrg: true,
  },
  {
    id: 'trendsData',
    label: 'Trends & Data',
    subTabs: [
      { id: 'trends', label: 'Trends' },
      { id: 'dataSources', label: 'Data Sources' },
    ],
  },
  {
    id: 'admin',
    label: 'Data Health',
    requiresAdmin: true,
    subTabs: [
      { id: 'pipelineHealth', label: 'Pipeline Health' },
    ],
  },
];

/** Map from legacy flat tab id → { group, sub } for redirect support. */
export const LEGACY_TAB_MAP: Record<string, { tab: string; sub?: string }> = (() => {
  const map: Record<string, { tab: string; sub?: string }> = {};
  for (const group of TAB_GROUPS) {
    if (group.subTabs) {
      for (const sub of group.subTabs) {
        map[sub.id] = { tab: group.id, sub: sub.id };
      }
    } else {
      map[group.id] = { tab: group.id };
    }
  }
  return map;
})();
