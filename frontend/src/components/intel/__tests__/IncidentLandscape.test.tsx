import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, cleanup, act } from '@testing-library/react';

vi.mock('../../../api/dashboardSummary', () => ({
  fetchGeographicHeatmap: vi.fn(),
  fetchSectorAttackMatrix: vi.fn(),
  fetchIndustryRisk: vi.fn(),
  fetchAttackTypes: vi.fn(),
}));

vi.mock('../../shared/SourceBadge', () => ({
  default: ({ datasetKey }: { datasetKey: string }) => (
    <span data-testid="source-badge">{datasetKey}</span>
  ),
}));

vi.mock('../../charts/CyberSecurityMap', () => ({
  default: () => <div data-testid="cyber-map" />,
}));
vi.mock('../../charts/SectorAttackHeatmap', () => ({
  default: () => <div data-testid="sector-heatmap" />,
}));
vi.mock('../../charts/SectorImpactTable', () => ({
  default: () => <div data-testid="sector-impact" />,
}));
vi.mock('../../charts/LossByAttackTypeChart', () => ({
  default: () => <div data-testid="loss-by-attack" />,
}));
vi.mock('../../charts/MalwareBarChart', () => ({
  default: () => <div data-testid="malware-chart" />,
}));

import IncidentLandscape from '../IncidentLandscape';
import {
  fetchGeographicHeatmap,
  fetchSectorAttackMatrix,
  fetchIndustryRisk,
  fetchAttackTypes,
} from '../../../api/dashboardSummary';

const mockGeo = vi.mocked(fetchGeographicHeatmap);
const mockMatrix = vi.mocked(fetchSectorAttackMatrix);
const mockRisk = vi.mocked(fetchIndustryRisk);
const mockTypes = vi.mocked(fetchAttackTypes);

const STUBS = ['cyber-map', 'sector-heatmap', 'sector-impact', 'loss-by-attack', 'malware-chart'];

beforeEach(() => {
  vi.clearAllMocks();
  mockGeo.mockResolvedValue({ items: [], year: null });
  mockMatrix.mockResolvedValue({ items: [], year: null });
  mockRisk.mockResolvedValue({ items: [], year: null });
  mockTypes.mockResolvedValue({ items: [], year: null });
});

describe('IncidentLandscape', () => {
  it('renders the heading and all five chart stubs', async () => {
    render(<IncidentLandscape />);
    expect(screen.getByRole('heading', { level: 3, name: 'Incident landscape' })).toBeInTheDocument();
    for (const id of STUBS) {
      expect(await screen.findByTestId(id)).toBeInTheDocument();
    }
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('shows source badges in order: geographic, sector matrix, then ic3_incidents x3', async () => {
    render(<IncidentLandscape />);
    await waitFor(() => expect(mockTypes).toHaveBeenCalled());
    const keys = screen.getAllByTestId('source-badge').map(b => b.textContent);
    expect(keys).toEqual([
      'ic3_geographic',
      'ic3_sector_attack_matrix',
      'ic3_incidents',
      'ic3_incidents',
      'ic3_incidents',
    ]);
  });

  it('keeps the other four widgets and shows one error line when the matrix fetch rejects', async () => {
    mockMatrix.mockRejectedValue(new Error('boom'));
    render(<IncidentLandscape />);
    const alerts = await screen.findAllByRole('alert');
    expect(alerts).toHaveLength(1);
    for (const id of STUBS) {
      expect(screen.getByTestId(id)).toBeInTheDocument();
    }
  });

  it('passes one shared signal to all four fetches and aborts it on unmount without an error', async () => {
    const { unmount } = render(<IncidentLandscape />);
    await waitFor(() => expect(mockTypes).toHaveBeenCalledTimes(1));
    const signals = [mockGeo, mockMatrix, mockRisk, mockTypes].map(m => m.mock.calls[0][0] as AbortSignal);
    expect(signals[0]).toBeInstanceOf(AbortSignal);
    expect(new Set(signals).size).toBe(1);
    expect(signals[0].aborted).toBe(false);
    unmount();
    expect(signals[0].aborted).toBe(true);
    cleanup();
  });

  it('does not show an error for requests rejected because they were aborted', async () => {
    let rejectMatrix: (e: unknown) => void = () => {};
    mockMatrix.mockImplementation(() => new Promise((_, rej) => { rejectMatrix = rej; }));
    render(<IncidentLandscape />);
    await waitFor(() => expect(mockMatrix).toHaveBeenCalled());
    await act(async () => {
      rejectMatrix(new DOMException('aborted', 'AbortError'));
    });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
});
