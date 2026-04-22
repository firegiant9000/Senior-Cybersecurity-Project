import React, { useState, useEffect, useCallback } from 'react';
import { API_BASE_URL, getJsonAuth } from '../../api/fetchWithAuth';
import { formatDateWithTz } from '../../utils/formatTime';

interface NormalizationLogItem {
  id: number;
  data_type: string;
  raw_value: string;
  normalized_value: string;
  confidence: number;
  method: string;
  org_id: number | null;
  created_at: string;
}

interface NormalizationLogResponse {
  items: NormalizationLogItem[];
  total: number;
  page: number;
  page_size: number;
}

const DATA_TYPES = ['vendor', 'industry', 'domain'];
const PAGE_SIZE = 25;

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 90 ? '#166534' : pct >= 70 ? '#854d0e' : '#991b1b';
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{
        width: 60, height: 8, borderRadius: 4,
        background: '#e5e7eb', overflow: 'hidden',
      }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 4 }} />
      </div>
      <span style={{ fontSize: 12, color, fontWeight: 600 }}>{pct}%</span>
    </div>
  );
}

const NormalizationLogTab: React.FC = () => {
  const [items, setItems] = useState<NormalizationLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [dataTypeFilter, setDataTypeFilter] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async (p: number, dt: string) => {
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({ page: String(p), page_size: String(PAGE_SIZE) });
      if (dt) params.set('data_type', dt);
      const result = await getJsonAuth<NormalizationLogResponse>(
        `${API_BASE_URL}/api/v1/ingest/normalization-log?${params}`,
        new AbortController().signal,
      );
      setItems(result.items);
      setTotal(result.total);
      setPage(p);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(1, dataTypeFilter);
  }, [load, dataTypeFilter]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="data-table-container">
      <h2>Normalization Log</h2>
      <p style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 16 }}>
        Audit trail of raw-to-normalized value mappings applied during data ingestion and org profile updates.
      </p>

      <div className="filter-controls" style={{ marginBottom: 16 }}>
        <div className="filter-group">
          <label htmlFor="norm-type-filter">Data Type</label>
          <select
            id="norm-type-filter"
            value={dataTypeFilter}
            onChange={e => { setDataTypeFilter(e.target.value); setPage(1); }}
          >
            <option value="">All types</option>
            {DATA_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <button className="reset-filters-btn" onClick={() => setDataTypeFilter('')}>
          Reset
        </button>
      </div>

      <div className="pagination-info">
        {total} record{total !== 1 ? 's' : ''}
      </div>

      {loading && <p>Loading…</p>}
      {error && <p className="error">Error: {error}</p>}

      {!loading && !error && items.length === 0 && (
        <div className="empty-state">
          <p>No normalization records found. Records are created when vendors, industries, or domains are normalized during profile updates or ingestion.</p>
        </div>
      )}

      {items.length > 0 && (
        <>
          <div className="table-scroll-wrapper">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th>
                  <th>Raw Value</th>
                  <th>Normalized Value</th>
                  <th>Method</th>
                  <th>Confidence</th>
                  <th>Org</th>
                  <th>Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {items.map(item => (
                  <tr key={item.id}>
                    <td>
                      <span style={{
                        padding: '2px 8px', borderRadius: 10, fontSize: 11, fontWeight: 600,
                        background: item.data_type === 'vendor' ? '#dbeafe'
                          : item.data_type === 'industry' ? '#f3e8ff' : '#fef3c7',
                        color: item.data_type === 'vendor' ? '#1e40af'
                          : item.data_type === 'industry' ? '#6b21a8' : '#92400e',
                      }}>
                        {item.data_type}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{item.raw_value}</td>
                    <td style={{ fontFamily: 'monospace', fontSize: 12 }}>{item.normalized_value}</td>
                    <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{item.method}</td>
                    <td><ConfidenceBar value={item.confidence} /></td>
                    <td style={{ fontSize: 12 }}>{item.org_id ?? '—'}</td>
                    <td style={{ fontSize: 12 }}>{formatDateWithTz(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="pagination-controls">
              <button disabled={page <= 1} onClick={() => void load(page - 1, dataTypeFilter)}>
                &larr; Previous
              </button>
              <span>Page {page} of {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => void load(page + 1, dataTypeFilter)}>
                Next &rarr;
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
};

export default NormalizationLogTab;
