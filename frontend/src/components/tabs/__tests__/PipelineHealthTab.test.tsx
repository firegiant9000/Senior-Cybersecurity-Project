import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent, within } from '@testing-library/react';

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
import {
  fetchIngestRuns,
  fetchIngestFreshness,
  triggerIngestion,
  retryIngestRun,
  cancelIngestRun,
} from '../../../api/ingest';
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

  describe('cancel and retry actions', () => {
    const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(50); });

    const freshness = (status: string, minutesAgo: number) => ({
      source: 'nvd',
      last_run_at: new Date(Date.now() - minutesAgo * 60000).toISOString(),
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

    const runItem = (status: string) => ({
      id: 'run-1',
      source: 'nvd',
      started_at: new Date().toISOString(),
      finished_at: null,
      status,
      records_ingested: 0,
      error_message: null,
      trigger: 'manual',
      retry_count: 0,
      skipped_reason: null,
      next_scheduled_at: null,
    });

    async function renderRunning() {
      vi.mocked(fetchIngestFreshness).mockResolvedValue({ sources: [freshness('running', 45)] });
      vi.mocked(fetchIngestRuns).mockResolvedValue({
        items: [runItem('running')], total: 1, page: 1, page_size: 15,
      } as never);
      render(<PipelineHealthTab />);
      await flush();
      fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));
      await flush();
      return screen.getByRole('alertdialog');
    }

    beforeEach(() => {
      vi.mocked(cancelIngestRun).mockClear();
      vi.mocked(retryIngestRun).mockClear();
      vi.mocked(triggerIngestion).mockClear();
      vi.mocked(cancelIngestRun).mockResolvedValue({ warning: null } as never);
      vi.mocked(retryIngestRun).mockResolvedValue({} as never);
    });

    it('shows the dialog and makes no call when the admin keeps the run', async () => {
      const dialog = await renderRunning();
      expect(within(dialog).getByText('Cancel ingest run')).toBeInTheDocument();
      expect(within(dialog).getByText(
        'Cancel the running nvd ingest? Data it has not written yet is lost.',
      )).toBeInTheDocument();
      fireEvent.click(within(dialog).getByRole('button', { name: 'Keep running' }));
      await flush();
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
      expect(cancelIngestRun).not.toHaveBeenCalled();
    });

    it('cancels once on Cancel run', async () => {
      const dialog = await renderRunning();
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel run' }));
      await flush();
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
      expect(cancelIngestRun).toHaveBeenCalledTimes(1);
      expect(cancelIngestRun).toHaveBeenCalledWith('run-1');
      expect(screen.getByText('Cancelled.')).toBeInTheDocument();
    });

    it('closes the dialog and shows the error when the cancel API rejects', async () => {
      vi.mocked(cancelIngestRun).mockRejectedValue(new Error('Cancel blew up'));
      const dialog = await renderRunning();
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel run' }));
      await flush();
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
      expect(screen.getByText('Cancel blew up')).toBeInTheDocument();
    });

    it('trigger and retry fire without a dialog', async () => {
      vi.mocked(fetchIngestFreshness).mockResolvedValue({ sources: [freshness('failed', 5)] });
      vi.mocked(fetchIngestRuns).mockResolvedValue({
        items: [runItem('failed')], total: 1, page: 1, page_size: 15,
      } as never);
      render(<PipelineHealthTab />);
      await flush();

      fireEvent.click(screen.getByRole('button', { name: 'Retry' }));
      await flush();
      expect(retryIngestRun).toHaveBeenCalledTimes(1);

      fireEvent.click(screen.getByRole('button', { name: /trigger ingestion/i }));
      await flush();
      expect(triggerIngestion).toHaveBeenCalledTimes(1);
      expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument();
    });
  });
});
