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
});
