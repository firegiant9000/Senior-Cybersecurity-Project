import React, { useState, useEffect } from 'react';
import { fetchIngestFreshness, type SourceFreshness } from '../../api/ingest';
import { FRESHNESS_REFRESH_EVENT } from './freshnessEvents';

const SOURCE_LABELS: Record<string, string> = {
  cisa_kev:   'CISA KEV',
  nvd:        'NVD',
  ic3:        'IC3',
  econ:       'Economics',
  economics:  'Economics',
  epss:       'EPSS',
};

const STATIC_LABELS: Record<string, string> = {
  ic3: 'static (2021–2025 annual reports)',
};

const POLL_INTERVAL_MS = 300_000;

function fmtAge(isoDate: string | null): string {
  if (!isoDate) return 'never';
  const ms = Date.now() - new Date(isoDate).getTime();
  const mins  = Math.floor(ms / 60_000);
  const hours = Math.floor(ms / 3_600_000);
  const days  = Math.floor(ms / 86_400_000);
  if (mins < 60)  return `${mins}m ago`;
  if (hours < 24) return `${hours}h ago`;
  return `${days}d ago`;
}

function getDisplayStatus(s: SourceFreshness): string {
  if (s.refresh_policy === 'static') return 'static';
  if (s.status === 'failed' || s.consecutive_failures > 0) return 'error';
  if (s.status === 'running') return 'running';
  if (s.stale) return 'stale';
  return s.status ?? 'unknown';
}

function getTooltip(s: SourceFreshness): string {
  const parts: string[] = [];
  if (s.consecutive_failures > 0) {
    parts.push(`${s.consecutive_failures} consecutive failure${s.consecutive_failures > 1 ? 's' : ''}`);
  }
  if (s.error_message) parts.push(s.error_message);
  if (s.last_successful_run_at) {
    parts.push(`Last success: ${fmtAge(s.last_successful_run_at)}`);
  }
  return parts.join(' · ');
}

const DataFreshness: React.FC = () => {
  const [sources, setSources] = useState<SourceFreshness[]>([]);

  useEffect(() => {
    let controller: AbortController | null = null;
    let timer: ReturnType<typeof setInterval> | null = null;

    const load = () => {
      controller?.abort();
      const c = new AbortController();
      controller = c;
      fetchIngestFreshness(c.signal)
        .then(r => { if (!c.signal.aborted) setSources(r.sources); })
        .catch(() => { /* non-fatal — hide silently */ });
    };
    const stop = () => {
      if (timer !== null) { clearInterval(timer); timer = null; }
    };
    const start = () => {
      stop();
      timer = setInterval(load, POLL_INTERVAL_MS);
    };
    const onVisibility = () => {
      if (document.hidden) {
        stop();
      } else {
        load();
        start();
      }
    };

    load();
    if (!document.hidden) start();
    document.addEventListener('visibilitychange', onVisibility);
    window.addEventListener(FRESHNESS_REFRESH_EVENT, load);
    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener(FRESHNESS_REFRESH_EVENT, load);
      stop();
      controller?.abort();
    };
  }, []);

  if (sources.length === 0) return null;

  return (
    <div className="freshness-bar">
      {sources.map(s => {
        const displayStatus = getDisplayStatus(s);
        const tooltip = getTooltip(s);
        return (
          <span
            key={s.source}
            className={`freshness-item freshness-${displayStatus}`}
            title={tooltip || undefined}
          >
            {SOURCE_LABELS[s.source] ?? s.source}
            {': '}
            {displayStatus === 'static'
              ? (STATIC_LABELS[s.source] ?? 'static')
              : fmtAge(s.last_run_at)}
            {displayStatus === 'error' && ' ⚠'}
            {displayStatus === 'stale' && ' ○'}
          </span>
        );
      })}
    </div>
  );
};

export default DataFreshness;
