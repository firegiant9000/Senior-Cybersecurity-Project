import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';

vi.mock('../../../api/ingest', () => ({
  fetchIngestFreshness: vi.fn(),
}));

import DataFreshness from '../DataFreshness';
import { fetchIngestFreshness, type SourceFreshness } from '../../../api/ingest';
import { requestFreshnessRefresh } from '../freshnessEvents';

const mockFetch = vi.mocked(fetchIngestFreshness);

let hidden = false;

function item(over: Partial<SourceFreshness>): SourceFreshness {
  return {
    source: 'nvd',
    last_run_at: new Date().toISOString(),
    last_successful_run_at: new Date().toISOString(),
    consecutive_failures: 0,
    status: 'success',
    records_ingested: 1,
    total_records: 1,
    error_message: null,
    trigger: 'scheduled',
    retry_count: 0,
    skipped_reason: null,
    refresh_policy: 'scheduled',
    stale: false,
    ...over,
  };
}

function ago(ms: number): string {
  return new Date(Date.now() - ms).toISOString();
}

async function renderBadge() {
  render(<DataFreshness />);
  await act(async () => { await Promise.resolve(); });
}

function setHidden(value: boolean) {
  hidden = value;
  act(() => { document.dispatchEvent(new Event('visibilitychange')); });
}

describe('DataFreshness', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    hidden = false;
    Object.defineProperty(document, 'hidden', { configurable: true, get: () => hidden });
    mockFetch.mockReset();
    mockFetch.mockResolvedValue({ sources: [item({})] });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('fetches on mount', async () => {
    await renderBadge();
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/NVD:/)).toBeInTheDocument();
  });

  it('refetches every 5 minutes', async () => {
    await renderBadge();
    await act(async () => { await vi.advanceTimersByTimeAsync(300_000); });
    expect(mockFetch).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(300_000); });
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });

  it('refetches on freshness:refresh', async () => {
    await renderBadge();
    await act(async () => { requestFreshnessRefresh(); await Promise.resolve(); });
    expect(mockFetch).toHaveBeenCalledTimes(2);
  });

  it('renders static source label', async () => {
    mockFetch.mockResolvedValue({
      sources: [item({
        source: 'ic3', refresh_policy: 'static', stale: false,
        consecutive_failures: 0, status: 'completed',
      })],
    });
    await renderBadge();
    const el = screen.getByText(/IC3:/);
    expect(el.textContent).toContain('IC3: static (2021–2025 annual reports)');
    expect(el).toHaveClass('freshness-static');
    expect(el.textContent).not.toContain('⚠');
    expect(el.textContent).not.toContain('○');
  });

  it('flags a failing static source with the warning glyph and error class', async () => {
    mockFetch.mockResolvedValue({
      sources: [item({
        source: 'ic3', refresh_policy: 'static', stale: true,
        consecutive_failures: 2, status: 'failed',
      })],
    });
    await renderBadge();
    const el = screen.getByText(/IC3:/);
    expect(el.textContent).toContain('IC3: static (2021–2025 annual reports)');
    expect(el.textContent).toContain('⚠');
    expect(el).toHaveClass('freshness-error');
    expect(el).not.toHaveClass('freshness-static');
  });

  it('renders a disabled source label', async () => {
    mockFetch.mockResolvedValue({
      sources: [item({
        source: 'economics', refresh_policy: 'disabled', stale: false,
        last_run_at: ago(40 * 86_400_000),
      })],
    });
    await renderBadge();
    const el = screen.getByText(/Economics:/);
    expect(el.textContent).toBe('Economics: disabled');
    expect(el).toHaveClass('freshness-static');
    expect(el.textContent).not.toContain('⚠');
  });

  it('flags a failing disabled source', async () => {
    mockFetch.mockResolvedValue({
      sources: [item({
        source: 'economics', refresh_policy: 'disabled', stale: false,
        consecutive_failures: 1, status: 'failed',
      })],
    });
    await renderBadge();
    const el = screen.getByText(/Economics:/);
    expect(el.textContent).toBe('Economics: disabled ⚠');
    expect(el).toHaveClass('freshness-error');
  });

  it('uses server stale flag', async () => {
    mockFetch.mockResolvedValue({
      sources: [
        item({ source: 'nvd', stale: true, last_run_at: ago(60_000), last_successful_run_at: ago(60_000) }),
        item({ source: 'epss', stale: false, last_run_at: ago(40 * 3_600_000), last_successful_run_at: ago(40 * 3_600_000) }),
      ],
    });
    await renderBadge();
    expect(screen.getByText(/NVD:/)).toHaveClass('freshness-stale');
    expect(screen.getByText(/EPSS:/)).not.toHaveClass('freshness-stale');
  });

  it('shows a run in progress as running even after an earlier failure', async () => {
    // consecutive_failures no longer resets on a running row, so a catch-up or
    // retry in flight after a failure must still read as running, not error.
    mockFetch.mockResolvedValue({
      sources: [
        item({ source: 'nvd', status: 'running', consecutive_failures: 1 }),
        item({ source: 'ic3', refresh_policy: 'static', status: 'running', consecutive_failures: 1 }),
      ],
    });
    await renderBadge();
    expect(screen.getByText(/NVD:/)).toHaveClass('freshness-running');
    expect(screen.getByText(/IC3:/)).toHaveClass('freshness-static');
  });

  it('does not poll while hidden', async () => {
    await renderBadge();
    setHidden(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(900_000); });
    expect(mockFetch).toHaveBeenCalledTimes(1);
  });

  it('refetches once when visible again', async () => {
    await renderBadge();
    setHidden(true);
    setHidden(false);
    await act(async () => { await Promise.resolve(); });
    expect(mockFetch).toHaveBeenCalledTimes(2);
    await act(async () => { await vi.advanceTimersByTimeAsync(300_000); });
    expect(mockFetch).toHaveBeenCalledTimes(3);
  });
});
