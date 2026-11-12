import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import RiskScoringTable from '../RiskScoringTable';

const { fetchWithAuth } = vi.hoisted(() => ({ fetchWithAuth: vi.fn() }));

vi.mock('../../../api/fetchWithAuth', () => ({ fetchWithAuth }));
vi.mock('../../../hooks/useDebounce', () => ({ useDebounce: (v: string) => v }));

const PAGE = {
  items: [],
  total: 0,
};

function urls(): string[] {
  return fetchWithAuth.mock.calls.map((c) => String(c[0]));
}

describe('RiskScoringTable summary toggle', () => {
  beforeEach(() => {
    fetchWithAuth.mockReset();
    fetchWithAuth.mockResolvedValue({ ok: true, json: async () => PAGE });
  });

  it('does not request /risk-scored/stats when showSummary is false', async () => {
    render(<RiskScoringTable apiBaseUrl="http://api" showSummary={false} />);
    await waitFor(() => expect(urls().some((u) => u.includes('/risk-scored?'))).toBe(true));
    expect(urls().some((u) => u.includes('/risk-scored/stats'))).toBe(false);
  });

  it('requests /risk-scored/stats by default', async () => {
    render(<RiskScoringTable apiBaseUrl="http://api" />);
    await waitFor(() => expect(urls().some((u) => u.includes('/risk-scored/stats'))).toBe(true));
    expect(screen.getByText(/Showing 0 of 0/)).toBeTruthy();
  });
});
