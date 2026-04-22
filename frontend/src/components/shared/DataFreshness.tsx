import React, { useState, useEffect } from 'react';
import { fetchIngestFreshness, type SourceFreshness } from '../../api/ingest';

const SOURCE_LABELS: Record<string, string> = {
  cisa_kev: 'CISA KEV',
  nvd:      'NVD',
  ic3:      'IC3',
  econ:     'Economics',
};

const STALE_THRESHOLD_MS = 24 * 60 * 60 * 1000;

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
  if (s.status === 'failed' || s.consecutive_failures > 0) return 'error';
  if (s.status === 'running') return 'running';
  const lastSuccess = s.last_successful_run_at ?? s.last_run_at;
  if (!lastSuccess || Date.now() - new Date(lastSuccess).getTime() > STALE_THRESHOLD_MS) {
    return 'stale';
  }
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
    const controller = new AbortController();
    fetchIngestFreshness(controller.signal)
      .then(r => setSources(r.sources))
      .catch(() => { /* non-fatal — hide silently */ });
    return () => controller.abort();
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
            {fmtAge(s.last_run_at)}
            {displayStatus === 'error' && ' ⚠'}
            {displayStatus === 'stale' && ' ○'}
          </span>
        );
      })}
    </div>
  );
};

export default DataFreshness;
