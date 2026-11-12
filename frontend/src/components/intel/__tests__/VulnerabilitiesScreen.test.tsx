import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import VulnerabilitiesScreen from '../VulnerabilitiesScreen';

vi.mock('../../../api/fetchWithAuth', () => ({ API_BASE_URL: 'http://api' }));
vi.mock('../VulnerabilitySummary', () => ({
  default: () => <div data-testid="summary-stub" />,
}));
vi.mock('../../tabs/RiskScoringTable', () => ({
  default: ({ showSummary }: { showSummary?: boolean }) => (
    <div data-testid="risk-stub" data-show-summary={String(showSummary)} />
  ),
}));
vi.mock('../../tabs/CisaKevTable', () => ({
  default: () => <div data-testid="kev-stub" />,
}));
vi.mock('../../tabs/NvdTable', () => ({
  default: () => <div data-testid="nvd-stub" />,
}));

function LocationProbe() {
  const location = useLocation();
  return <div data-testid="location">{location.search}</div>;
}

function renderAt(url: string) {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <VulnerabilitiesScreen />
      <LocationProbe />
    </MemoryRouter>,
  );
}

describe('VulnerabilitiesScreen', () => {
  it('shows the heading and summary', () => {
    renderAt('/vulnerabilities');
    expect(screen.getByRole('heading', { name: 'Vulnerabilities' })).toBeTruthy();
    expect(screen.getByTestId('summary-stub')).toBeTruthy();
  });

  it('defaults to the risk-scored table without its own summary', () => {
    renderAt('/vulnerabilities');
    const stub = screen.getByTestId('risk-stub');
    expect(stub.getAttribute('data-show-summary')).toBe('false');
    expect(screen.queryByTestId('kev-stub')).toBeNull();
  });

  it('shows the KEV table for ?source=kev', () => {
    renderAt('/vulnerabilities?source=kev');
    expect(screen.getByTestId('kev-stub')).toBeTruthy();
    expect(screen.queryByTestId('risk-stub')).toBeNull();
  });

  it('falls back to risk-scored for an unknown source', () => {
    renderAt('/vulnerabilities?source=zzz');
    expect(screen.getByTestId('risk-stub')).toBeTruthy();
  });

  it('switches to NVD on click and keeps other params', () => {
    renderAt('/vulnerabilities?source=kev&q=1');
    fireEvent.click(screen.getByRole('tab', { name: 'NVD' }));
    const search = new URLSearchParams(screen.getByTestId('location').textContent ?? '');
    expect(search.get('source')).toBe('nvd');
    expect(search.get('q')).toBe('1');
    expect(screen.getByTestId('nvd-stub')).toBeTruthy();
    expect(screen.queryByTestId('kev-stub')).toBeNull();
  });
});
