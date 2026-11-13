import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';

const { mockUser } = vi.hoisted(() => ({ mockUser: { id: 'u1', email: 'user@example.com' } }));

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({ user: mockUser }),
}));

vi.mock('../../../api/anomalies', () => ({
  fetchIC3Anomalies: vi.fn(),
  fetchTrendAnomalies: vi.fn(),
  fetchVendorAnomalies: vi.fn(),
}));

import AnomaliesTab from '../AnomaliesTab';
import {
  fetchIC3Anomalies,
  fetchTrendAnomalies,
  fetchVendorAnomalies,
} from '../../../api/anomalies';

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.pathname}</div>;
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/intel/anomalies/:view" element={<AnomaliesTab />} />
      </Routes>
      <LocationProbe />
    </MemoryRouter>,
  );
}

describe('AnomaliesTab view routing', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchIC3Anomalies).mockResolvedValue({ total: 0, threshold: 2, items: [] } as never);
    vi.mocked(fetchTrendAnomalies).mockResolvedValue({ threshold_pct: 0.2, items: [] } as never);
    vi.mocked(fetchVendorAnomalies).mockResolvedValue({
      has_vendors: false,
      items: [],
      org_total_matches: 0,
      global_avg_total: 0,
      threshold: 2,
    } as never);
  });

  it('loads the vendor view and marks its link as current at /intel/anomalies/vendors', async () => {
    renderAt('/intel/anomalies/vendors');

    expect(await screen.findByText(/No vendors configured/)).toBeInTheDocument();
    expect(fetchVendorAnomalies).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('link', { name: 'Vendor Exposure' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'IC3 State Anomalies' })).not.toHaveAttribute('aria-current');
  });

  it('redirects an unknown view to /intel/anomalies/ic3 without fetching the other views', async () => {
    renderAt('/intel/anomalies/zzz');

    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/intel/anomalies/ic3'));
    await waitFor(() => expect(fetchIC3Anomalies).toHaveBeenCalledTimes(1));
    expect(fetchTrendAnomalies).not.toHaveBeenCalled();
    expect(fetchVendorAnomalies).not.toHaveBeenCalled();
  });

  it('renders the three controls as links to their view paths', async () => {
    renderAt('/intel/anomalies/ic3');

    expect(await screen.findByText(/No anomalies detected at the current threshold/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'IC3 State Anomalies' })).toHaveAttribute('href', '/intel/anomalies/ic3');
    expect(screen.getByRole('link', { name: 'YoY Trends' })).toHaveAttribute('href', '/intel/anomalies/trends');
    expect(screen.getByRole('link', { name: 'Vendor Exposure' })).toHaveAttribute('href', '/intel/anomalies/vendors');
  });
});
