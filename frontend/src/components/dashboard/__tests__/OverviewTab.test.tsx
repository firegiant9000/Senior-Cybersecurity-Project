import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within, fireEvent } from '@testing-library/react';

// Overview is a fixed layout: no widget grid, no Customize, no Executive Summary.

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
  default: ({ data }: { data: unknown }) => (
    <div data-testid="projected-loss">{JSON.stringify(data)}</div>
  ),
}));
vi.mock('../NextStepsCard', () => ({
  default: () => <div data-testid="next-steps" />,
}));
vi.mock('../../shared/AssessmentBanner', () => ({
  default: () => <div data-testid="assessment-banner" />,
}));
vi.mock('../../shared/DataFreshness', () => ({
  default: () => <div data-testid="data-freshness" />,
}));

import OverviewTab from '../OverviewTab';
import type { DashboardData } from '../../../hooks/useDashboardData';

const fullData = {
  summary: null,
  executiveSummary: null,
  lossProjection: { marker: 'projection-data' },
  attackTypes: [],
  industryRisk: [],
  geographicThreats: [],
  severityDistribution: [],
  sectorAttackMatrix: [],
  temporalTrends: [],
  kevTotal: 0,
  riskScoreStats: null,
  ic3AnomalyCount: null,
  escalatingSectorCount: null,
} as unknown as DashboardData;

function renderTab(onRefresh = vi.fn(), errors: string[] = []) {
  render(
    <OverviewTab
      data={fullData}
      loading={false}
      loadingHeavy={false}
      errors={errors}
      lastUpdated={null}
      onRefresh={onRefresh}
    />,
  );
  return onRefresh;
}

function before(a: HTMLElement, b: HTMLElement) {
  return Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
}

describe('OverviewTab (fixed layout)', () => {
  let getItemSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    localStorage.clear();
    getItemSpy = vi.spyOn(window.Storage.prototype, 'getItem');
  });

  afterEach(() => {
    getItemSpy.mockRestore();
  });

  it('renders the seven cards, with the toolbar and errors banner, in order', () => {
    renderTab(vi.fn(), ['Loss projection: failed']);
    const ordered = [
      screen.getByTestId('assessment-banner'),
      screen.getByTestId('next-steps'),
      screen.getByRole('button', { name: /refresh dashboard data/i }),
      screen.getByTestId('data-freshness'),
      screen.getByText(/some widgets failed to load/i),
      screen.getByTestId('inventory-health'),
      screen.getByTestId('vendor-alerts'),
      screen.getByTestId('projected-loss'),
      screen.getByTestId('threat-overview'),
      screen.getByTestId('emerging-threats'),
    ];
    for (let i = 0; i < ordered.length - 1; i++) {
      expect(before(ordered[i], ordered[i + 1])).toBe(true);
    }
  });

  it('passes lossProjection to ProjectedLossCard', () => {
    renderTab();
    expect(screen.getByTestId('projected-loss')).toHaveTextContent('projection-data');
  });

  it('has no Customize or Tabs button and no Executive Summary heading', () => {
    renderTab();
    expect(screen.queryByRole('button', { name: /customi[sz]e/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /tabs/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Executive Summary' })).not.toBeInTheDocument();
    expect(screen.queryByText('Executive Summary')).not.toBeInTheDocument();
  });

  it('prints the vendor_alerts, loss_projection and kev source badges', () => {
    renderTab();
    const keys = screen.getAllByTestId('source-badge').map((b) => b.textContent);
    expect(keys).toEqual(['vendor_alerts', 'loss_projection', 'kev']);
    const vendor = screen.getByTestId('vendor-alerts').parentElement as HTMLElement;
    expect(within(vendor).getByText('vendor_alerts')).toBeInTheDocument();
    const loss = screen.getByTestId('projected-loss').parentElement as HTMLElement;
    expect(within(loss).getByText('loss_projection')).toBeInTheDocument();
    const kev = screen.getByTestId('emerging-threats').parentElement as HTMLElement;
    expect(within(kev).getByText('kev')).toBeInTheDocument();
  });

  it('never reads overviewWidgetPrefs from localStorage', () => {
    renderTab();
    expect(getItemSpy).not.toHaveBeenCalledWith('overviewWidgetPrefs');
  });

  it('calls onRefresh when Refresh is clicked', () => {
    const onRefresh = renderTab();
    fireEvent.click(screen.getByRole('button', { name: /refresh dashboard data/i }));
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });
});
