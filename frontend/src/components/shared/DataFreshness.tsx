import React, { useState, useEffect } from 'react';
import { fetchIngestFreshness, type SourceFreshness } from '../../api/ingest';

const SOURCE_LABELS: Record<string, string> = {
  cisa_kev: 'CISA KEV',
  nvd:      'NVD',
  ic3:      'IC3',
  econ:     'Economics',
};

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
      {sources.map(s => (
        <span key={s.source} className={`freshness-item freshness-${s.status ?? 'unknown'}`}>
          {SOURCE_LABELS[s.source] ?? s.source}
          {': '}
          {fmtAge(s.last_run_at)}
        </span>
      ))}
    </div>
  );
};

export default DataFreshness;
