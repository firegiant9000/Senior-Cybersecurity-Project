import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => ({ role: 'admin' }),
}));

vi.mock('../../../api/ingest', () => ({
  fetchIngestRuns: vi.fn(),
  fetchIngestFreshness: vi.fn(),
  triggerIngestion: vi.fn(),
  retryIngestRun: vi.fn(),
  cancelIngestRun: vi.fn(),
}));

import PipelineHealthTab from '../PipelineHealthTab';
import { fetchIngestRuns, fetchIngestFreshness, triggerIngestion } from '../../../api/ingest';
import { FRESHNESS_REFRESH_EVENT } from '../../shared/freshnessEvents';

describe('PipelineHealthTab', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(fetchIngestRuns).mockResolvedValue({ items: [], total: 0, page: 1, page_size: 15 } as never);
    vi.mocked(fetchIngestFreshness).mockResolvedValue({ sources: [] });
    vi.mocked(triggerIngestion).mockResolvedValue({ message: 'ok' } as never);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('dispatches freshness:refresh after the 2 s refresh timer, not on trigger', async () => {
    const listener = vi.fn();
    window.addEventListener(FRESHNESS_REFRESH_EVENT, listener);
    try {
      render(<PipelineHealthTab />);
      await act(async () => { await Promise.resolve(); });

      fireEvent.click(screen.getByRole('button', { name: /trigger ingestion/i }));
      await act(async () => { await Promise.resolve(); });
      expect(listener).toHaveBeenCalledTimes(0);

      await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
      expect(listener).toHaveBeenCalledTimes(0);

      await act(async () => { await vi.advanceTimersByTimeAsync(1); });
      expect(listener).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener(FRESHNESS_REFRESH_EVENT, listener);
    }
  });

  it('re-fetches its own freshness after the 2 s timer', async () => {
    render(<PipelineHealthTab />);
    await act(async () => { await Promise.resolve(); });
    const before = vi.mocked(fetchIngestFreshness).mock.calls.length;

    fireEvent.click(screen.getByRole('button', { name: /trigger ingestion/i }));
    await act(async () => { await Promise.resolve(); });
    await act(async () => { await vi.advanceTimersByTimeAsync(1999); });
    expect(vi.mocked(fetchIngestFreshness).mock.calls.length).toBe(before);

    await act(async () => { await vi.advanceTimersByTimeAsync(1); });
    expect(vi.mocked(fetchIngestFreshness).mock.calls.length).toBe(before + 1);
  });

  it('picks up a running source after a trigger and fires a second refresh when it goes idle', async () => {
    const source = (status: string) => ({
      source: 'nvd',
      last_run_at: new Date().toISOString(),
      last_successful_run_at: null,
      consecutive_failures: 0,
      status,
      records_ingested: 0,
      total_records: 0,
      error_message: null,
      trigger: 'manual',
      retry_count: 0,
      skipped_reason: null,
      refresh_policy: 'scheduled' as const,
      stale: false,
    });
    vi.mocked(fetchIngestFreshness)
      .mockResolvedValueOnce({ sources: [] })                       // mount
      .mockResolvedValueOnce({ sources: [source('running')] })      // after the 2 s timer
      .mockResolvedValue({ sources: [source('completed')] });       // later polls

    const listener = vi.fn();
    window.addEventListener(FRESHNESS_REFRESH_EVENT, listener);
    try {
      render(<PipelineHealthTab />);
      await act(async () => { await Promise.resolve(); });

      fireEvent.click(screen.getByRole('button', { name: /trigger ingestion/i }));
      await act(async () => { await Promise.resolve(); });
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      expect(listener).toHaveBeenCalledTimes(1);
      expect(screen.getByText('Ingesting…')).toBeInTheDocument();

      await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
      expect(screen.queryByText('Ingesting…')).not.toBeInTheDocument();
      expect(listener).toHaveBeenCalledTimes(2);
    } finally {
      window.removeEventListener(FRESHNESS_REFRESH_EVENT, listener);
    }
  });
});
