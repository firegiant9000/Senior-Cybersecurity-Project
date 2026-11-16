import { describe, it, expect, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router';
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

  describe('tab semantics', () => {
    const sourceOf = () =>
      new URLSearchParams(screen.getByTestId('location').textContent ?? '').get('source');

    it('tabpanel is labelled by the selected tab', () => {
      renderAt('/vulnerabilities');
      const selected = screen.getByRole('tab', { selected: true });
      expect(screen.getByRole('tabpanel').getAttribute('aria-labelledby')).toBe(selected.id);
      expect(selected.getAttribute('aria-controls')).toBe('vuln-panel');
    });

    it('ArrowRight moves from Risk-scored to CISA KEV and updates the URL', () => {
      renderAt('/vulnerabilities');
      fireEvent.keyDown(screen.getByRole('tab', { name: 'Risk-scored' }), { key: 'ArrowRight' });
      const kev = screen.getByRole('tab', { name: 'CISA KEV' });
      expect(kev.getAttribute('aria-selected')).toBe('true');
      expect(document.activeElement).toBe(kev);
      expect(screen.getByTestId('location').textContent).toContain('source=kev');
    });

    it('ArrowLeft from Risk-scored wraps to NVD', () => {
      renderAt('/vulnerabilities');
      fireEvent.keyDown(screen.getByRole('tab', { name: 'Risk-scored' }), { key: 'ArrowLeft' });
      expect(sourceOf()).toBe('nvd');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'NVD' }));
    });

    it('End selects NVD', () => {
      renderAt('/vulnerabilities');
      fireEvent.keyDown(screen.getByRole('tab', { name: 'Risk-scored' }), { key: 'End' });
      expect(sourceOf()).toBe('nvd');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'NVD' }));
    });

    it('Alt+ArrowRight is left to the browser and does not change the tab', () => {
      renderAt('/vulnerabilities');
      const tab = screen.getByRole('tab', { name: 'Risk-scored' });
      fireEvent.keyDown(tab, { key: 'ArrowRight', altKey: true });
      expect(tab.getAttribute('aria-selected')).toBe('true');
      expect(screen.getByTestId('location').textContent).toBe('');
    });

    it('Home selects Risk-scored', () => {
      renderAt('/vulnerabilities?source=nvd');
      fireEvent.keyDown(screen.getByRole('tab', { name: 'NVD' }), { key: 'Home' });
      expect(sourceOf()).toBe('scored');
      expect(document.activeElement).toBe(screen.getByRole('tab', { name: 'Risk-scored' }));
    });
  });
});
