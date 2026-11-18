import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, act, fireEvent, within, waitFor } from '@testing-library/react';

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
import { fetchIngestRuns, fetchIngestFreshness, cancelIngestRun } from '../../../api/ingest';

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

async function openCancelDialog() {
  const cancel = await screen.findByRole('button', { name: 'Cancel' });
  cancel.focus();
  fireEvent.click(cancel);
  return { cancel, dialog: screen.getByRole('alertdialog') };
}

describe('PipelineHealthTab focus after cancel', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(fetchIngestRuns).mockResolvedValue({
      items: [runItem('running')], total: 1, page: 1, page_size: 15,
    } as never);
  });

  it("cancel success focuses that card's Retry", async () => {
    let resolveAfter!: (v: { sources: ReturnType<typeof freshness>[] }) => void;
    const deferred = new Promise<{ sources: ReturnType<typeof freshness>[] }>((res) => { resolveAfter = res; });
    let cancelled = false;
    vi.mocked(fetchIngestFreshness).mockImplementation(() =>
      cancelled
        ? (deferred as never)
        : Promise.resolve({ sources: [freshness('running', 45)] }),
    );
    vi.mocked(cancelIngestRun).mockImplementation(async () => {
      cancelled = true;
      return { warning: null } as never;
    });

    render(<PipelineHealthTab />);
    const { dialog } = await openCancelDialog();

    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel run' }));
    })
    await act(async () => {});

    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument();
    expect(document.activeElement).not.toBe(screen.getByRole('heading', { name: 'Pipeline Health' }));

    await act(async () => {
      resolveAfter({ sources: [freshness('failed', 45)] });
    });

    await waitFor(() =>
      expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Retry' })),
    );
  });

  it('a poll answered after the post-cancel refresh does not undo it', async () => {
    let resolveStale!: (v: { sources: ReturnType<typeof freshness>[] }) => void;
    const stale = new Promise<{ sources: ReturnType<typeof freshness>[] }>((res) => { resolveStale = res; });
    let cancelled = false;
    let calls = 0;
    vi.mocked(fetchIngestFreshness).mockImplementation(() => {
      calls += 1;
      if (cancelled) return Promise.resolve({ sources: [freshness('failed', 45)] });
      // The initial load answers; every poll after it is still in flight.
      return calls === 1 ? Promise.resolve({ sources: [freshness('running', 45)] }) : (stale as never);
    });
    vi.mocked(cancelIngestRun).mockImplementation(async () => {
      cancelled = true;
      return { warning: null } as never;
    });

    render(<PipelineHealthTab />);
    await screen.findByRole('button', { name: 'Cancel' });
    // Let the 1 s poll fire at least once before cancelling.
    await waitFor(() => expect(calls).toBeGreaterThanOrEqual(2), { timeout: 3000 });
    const { dialog } = await openCancelDialog();

    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel run' }));
    });
    const retry = await screen.findByRole('button', { name: 'Retry' });
    await waitFor(() => expect(document.activeElement).toBe(retry));

    await act(async () => {
      resolveStale({ sources: [freshness('running', 45)] });
    });

    expect(screen.getByRole('button', { name: 'Retry' })).toBe(retry);
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
    expect(document.activeElement).toBe(retry);
  });

  it('cancel failure returns focus to the cancel button', async () => {
    vi.mocked(fetchIngestFreshness).mockResolvedValue({ sources: [freshness('running', 45)] });
    vi.mocked(cancelIngestRun).mockRejectedValue(new Error('nope'));

    render(<PipelineHealthTab />);
    const { cancel, dialog } = await openCancelDialog();

    await act(async () => {
      fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel run' }));
    });

    await waitFor(() => expect(document.activeElement).toBe(cancel));
    expect(screen.getByText('nope')).toBeInTheDocument();
  });
});
