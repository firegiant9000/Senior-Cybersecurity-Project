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

let cachedState: DataStatusState | null = null;
let inflight: Promise<DataStatusState> | null = null;

async function load(signal: AbortSignal): Promise<DataStatusState> {
  if (cachedState && !cachedState.loading && !cachedState.error) return cachedState;
  if (inflight) return inflight;
  inflight = (async () => {
    try {
      const res = await fetchDataStatus(signal);
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
      cachedState = next;
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
    const controller = new AbortController();
    let active = true;
    load(controller.signal).then((next) => {
      if (active) setState(next);
    });
    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  return state;
}
