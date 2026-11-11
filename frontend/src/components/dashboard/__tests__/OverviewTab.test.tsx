import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';

// Characterisation tests for OverviewTab: they pin what renders today (widgets,
// data rows, source badges, refresh), not layout or internal structure.

vi.mock('recharts', async () => {
  const actual = await vi.importActual<typeof import('recharts')>('recharts');
  return {
    ...actual,
    // jsdom has no layout, so give charts a fixed size so axis labels render.
    ResponsiveContainer: ({ children }: { children: React.ReactElement }) =>
      React.cloneElement(children, { width: 800, height: 400 } as Record<string, unknown>),
  };
});

vi.mock('../../../api/ingest', () => ({
  fetchIngestFreshness: vi.fn(() => Promise.resolve({ sources: [] })),
}));

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({ role: 'user', orgRole: 'member', orgId: 1 }),
}));

vi.mock('../../shared/SourceBadge', () => ({
  default: ({ datasetKey }: { datasetKey: string }) => (
    <span data-testid="source-badge">{datasetKey}</span>
  ),
}));

vi.mock('../ThreatOverviewWidget', () => ({
  default: () => <div data-testid="threat-overview" />,
}));
vi.mock('../../shared/VendorAlertsCard', () => ({
  default: () => <div data-testid="vendor-alerts" />,
}));
vi.mock('../InventoryHealthCard', () => ({
  default: () => <div data-testid="inventory-health" />,
}));
vi.mock('../EmergingThreatsCard', () => ({
  default: () => <div data-testid="emerging-threats" />,
}));
vi.mock('../ProjectedLossCard', () => ({
  default: () => <div data-testid="projected-loss" />,
}));
vi.mock('../ExecutiveSummaryCard', () => ({
  default: () => <div data-testid="executive-summary" />,
}));
vi.mock('../NextStepsCard', () => ({ default: () => null }));
vi.mock('../../shared/AssessmentBanner', () => ({ default: () => null }));
vi.mock('../../shared/DataFreshness', () => ({ default: () => null }));
vi.mock('../../charts/CyberSecurityMap', () => ({
  default: () => <div data-testid="cyber-map" />,
}));
vi.mock('../../charts/SectorAttackHeatmap', () => ({
  default: () => <div data-testid="sector-heatmap" />,
}));
vi.mock('../../charts/MalwareBarChart', () => ({
  default: () => <div data-testid="malware-chart" />,
}));

import OverviewTab from '../OverviewTab';
import type { DashboardData } from '../../../hooks/useDashboardData';

const STORAGE_KEY = 'overviewWidgetPrefs';

// Mirrors the widgets hidden on a fresh login (useWidgetPrefs DEFAULT_HIDDEN).
const DEFAULT_HIDDEN = [
  'malwareChart', 'totalAttempts', 'totalLosses', 'progression',
  'avgLoss', 'cvesExploited', 'attackTypeCount', 'stateCount',
  'totalCves', 'ic3Anomalies', 'escalatingSectors',
  'incidentMgmt', 'cyberRisks', 'heatmap',
  'lossAttack', 'avgLossSector', 'complaintsSector', 'sectorTable',
];

function enableWidgets(...ids: string[]) {
  localStorage.setItem(
    STORAGE_KEY,
    JSON.stringify({ hidden: DEFAULT_HIDDEN.filter((id) => !ids.includes(id)), gridOrder: [] }),
  );
}

const fullData: DashboardData = {
  summary: {
    total_complaints: 1000,
    total_losses: 5_000_000,
    avg_loss_per_incident: 5000,
    attack_type_count: 2,
    sector_count: 2,
    state_count: 2,
  },
  executiveSummary: null,
  lossProjection: null,
  attackTypes: [
    { attack_type: 'Phishing', total_loss: 3_000_000, avg_loss: 300, complaint_count: 10000 },
    { attack_type: 'Ransomware', total_loss: 2_000_000, avg_loss: 900, complaint_count: 2000 },
  ],
  industryRisk: [
    { sector: 'Healthcare', complaint_count: 1234, total_loss: 4_500_000, avg_loss_per_incident: 3647 },
    { sector: 'Education', complaint_count: 321, total_loss: 800_000, avg_loss_per_incident: 2492 },
  ],
  geographicThreats: [],
  severityDistribution: [{ severity: 'CRITICAL', count: 10 }],
  sectorAttackMatrix: [],
  temporalTrends: [
    { year: 2024, complaint_count: 120, total_loss: 2000, avg_loss_per_incident: 16 },
    { year: 2023, complaint_count: 100, total_loss: 1000, avg_loss_per_incident: 10 },
  ],
  kevTotal: 3,
  riskScoreStats: {
    bands: [
      { label: 'Critical (80-100)', min: 80, max: 100, count: 5 },
      { label: 'Low (0-39)', min: 0, max: 39, count: 45 },
    ],
    top_vendors: [],
    avg_risk: 42,
    total: 50,
  } as DashboardData['riskScoreStats'],
  ic3AnomalyCount: null,
  escalatingSectorCount: null,
};

function renderTab(onRefresh = vi.fn()) {
  render(
    <OverviewTab
      data={fullData}
      loading={false}
      loadingHeavy={false}
      errors={[]}
      lastUpdated={null}
      onRefresh={onRefresh}
    />,
  );
  return onRefresh;
}

describe('OverviewTab (characterisation)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('renders ThreatOverviewWidget, VendorAlertsCard and InventoryHealthCard by default', () => {
    renderTab();
    expect(screen.getByTestId('threat-overview')).toBeInTheDocument();
    expect(screen.getByTestId('vendor-alerts')).toBeInTheDocument();
    expect(screen.getByTestId('inventory-health')).toBeInTheDocument();
  });

  it('shows the default grid widgets and hides the rest', () => {
    renderTab();
    expect(screen.getByText('Where Cyber Crime Hits Hardest (FBI IC3)')).toBeInTheDocument();
    expect(screen.getByTestId('cyber-map')).toBeInTheDocument();
    expect(screen.getByTestId('projected-loss')).toBeInTheDocument();
    expect(screen.getByTestId('emerging-threats')).toBeInTheDocument();
    expect(screen.getByText(/avg cve risk score/i)).toBeInTheDocument();
    expect(screen.getByText('CVE Risk Distribution')).toBeInTheDocument();

    // Hidden by default
    expect(screen.queryByText('Total Financial Loss by Attack Type')).not.toBeInTheDocument();
    expect(screen.queryByText('Sector Impact Summary')).not.toBeInTheDocument();
    expect(screen.queryByTestId('sector-heatmap')).not.toBeInTheDocument();
    expect(screen.queryByTestId('malware-chart')).not.toBeInTheDocument();
  });

  it('renders attack-type and sector rows when lossAttack and sectorTable are enabled', () => {
    enableWidgets('lossAttack', 'sectorTable');
    renderTab();

    const lossCard = screen.getByText('Total Financial Loss by Attack Type').closest('.card') as HTMLElement;
    expect(within(lossCard).getByText('Phishing')).toBeInTheDocument();
    expect(within(lossCard).getByText('Ransomware')).toBeInTheDocument();

    const sectorCard = screen.getByText('Sector Impact Summary').closest('.card') as HTMLElement;
    const rows = within(sectorCard).getAllByRole('row');
    // header + 2 rows, sorted by total loss descending
    expect(rows).toHaveLength(3);
    expect(within(rows[1]).getByText('Healthcare')).toBeInTheDocument();
    expect(within(rows[1]).getByText('1,234')).toBeInTheDocument();
    expect(within(rows[1]).getByText('$4,500,000')).toBeInTheDocument();
    expect(within(rows[1]).getByText('$3,647')).toBeInTheDocument();
    expect(within(rows[2]).getByText('Education')).toBeInTheDocument();
    expect(within(rows[2]).getByText('$800,000')).toBeInTheDocument();
  });

  it('shows a SourceBadge with the right dataset key on each of the five widgets', () => {
    enableWidgets('cyberMap', 'heatmap', 'malwareChart', 'lossAttack', 'sectorTable');
    renderTab();

    const badgeKeys = (testId: string) => {
      const wrapper = screen.getByTestId(testId).closest('.widget-drag-wrapper') as HTMLElement;
      return within(wrapper).getAllByTestId('source-badge').map((b) => b.textContent);
    };
    const badgeKeysForText = (text: string) => {
      const wrapper = screen.getByText(text).closest('.widget-drag-wrapper') as HTMLElement;
      return within(wrapper).getAllByTestId('source-badge').map((b) => b.textContent);
    };

    expect(badgeKeys('cyber-map')).toEqual(['ic3_geographic']);
    expect(badgeKeys('sector-heatmap')).toEqual(['ic3_sector_attack_matrix']);
    expect(badgeKeys('malware-chart')).toEqual(['ic3_incidents']);
    expect(badgeKeysForText('Total Financial Loss by Attack Type')).toEqual(['ic3_incidents']);
    expect(badgeKeysForText('Sector Impact Summary')).toEqual(['ic3_incidents']);
  });

  it('calls onRefresh when Refresh is clicked', () => {
    const onRefresh = renderTab();
    fireEvent.click(screen.getByRole('button', { name: /refresh dashboard data/i }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
