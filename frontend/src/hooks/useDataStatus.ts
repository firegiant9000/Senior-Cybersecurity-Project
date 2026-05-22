import { useEffect, useState } from "react";
import { fetchDataStatus, type DatasetStatus } from "../api/dataStatus";

interface DataStatusState {
  byKey: Record<string, DatasetStatus>;
  items: DatasetStatus[];
  loading: boolean;
  error: string | null;
}

const EMPTY_STATE: DataStatusState = {
  byKey: {},
  items: [],
  loading: true,
  error: null,
};

// Singleton cache. The fetch lifecycle is owned by this module, NOT by the
// component that happens to call `load()` first — under React 18 strict mode
// the first mount's cleanup would otherwise abort the shared request before
// the re-mount could observe it.
let cachedState: DataStatusState | null = null;
let inflight: Promise<DataStatusState> | null = null;

function load(): Promise<DataStatusState> {
  if (cachedState && !cachedState.loading && !cachedState.error) {
    return Promise.resolve(cachedState);
  }
  if (inflight) return inflight;
  // The singleton owns its own AbortController so component unmounts can't
  // kill the request. We never call abort() on it; it lives until the fetch
  // settles.
  const internalController = new AbortController();
  inflight = (async () => {
    try {
      const res = await fetchDataStatus(internalController.signal);
      const byKey: Record<string, DatasetStatus> = {};
      for (const it of res.items) byKey[it.key] = it;
      const next: DataStatusState = { byKey, items: res.items, loading: false, error: null };
      cachedState = next;
      return next;
    } catch (e) {
      const next: DataStatusState = {
        ...EMPTY_STATE,
        loading: false,
        error: e instanceof Error ? e.message : "Failed to load data status",
      };
      // Do not cache the error — let the next caller retry rather than
      // showing a stale failure forever.
      cachedState = null;
      return next;
    } finally {
      inflight = null;
    }
  })();
  return inflight;
}

/** Hook over the cached `/api/v1/data-status` response. Shared singleton cache. */
export function useDataStatus(): DataStatusState {
  const [state, setState] = useState<DataStatusState>(cachedState ?? EMPTY_STATE);

  useEffect(() => {
    if (cachedState && !cachedState.loading && !cachedState.error) {
      setState(cachedState);
      return;
    }
    let active = true;
    load().then((next) => {
      if (active) setState(next);
    });
    return () => {
      // Only gates setState — the underlying fetch keeps running so a
      // sibling component (or the re-mount under StrictMode) can observe it.
      active = false;
    };
  }, []);

  return state;
}
