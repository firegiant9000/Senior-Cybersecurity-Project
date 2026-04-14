import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { fetchVendorAlerts, VendorAlertsResponse } from '../../api/vendorAlerts';
import { useAuth } from '../../context/AuthContext';
import SeverityBadge from '../shared/SeverityBadge';

const VendorAlertsTab: React.FC = () => {
  const { user } = useAuth();
  const [data, setData] = useState<VendorAlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const load = useCallback(async (p: number) => {
    if (!user) return;
    setLoading(true);
    setError('');
    try {
      const result = await fetchVendorAlerts(p, pageSize);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [user]);

  useEffect(() => {
    load(page);
  }, [page, load]);

  if (!user) {
    return <div className="tab-page"><p>Please log in to view vendor alerts.</p></div>;
  }

  if (loading && !data) {
    return <div className="tab-page"><p>Loading vendor alerts...</p></div>;
  }

  if (error) {
    return (
      <div className="tab-page">
        <p style={{ color: '#d32f2f' }}>{error}</p>
        <button className="overview-refresh-btn" onClick={() => load(page)}>Retry</button>
      </div>
    );
  }

  if (!data || data.reason === 'no_vendors') {
    return (
      <div className="tab-page">
        <div style={{
          background: 'var(--card-bg, #1e293b)',
          border: '1px solid var(--border, #334155)',
          borderRadius: 8,
          padding: '20px 24px',
          maxWidth: 480,
        }}>
          <p style={{ fontWeight: 700, color: 'var(--text-primary, #e2e8f0)', marginBottom: 8 }}>
            No vendors configured
          </p>
          <p style={{ fontSize: 13, color: 'var(--text-secondary, #94a3b8)', marginBottom: 16 }}>
            Add your technology stack in Organization Settings. We'll match your vendors against the CISA Known Exploited Vulnerabilities catalog and alert you to active threats.
          </p>
          <Link
            to="/settings"
            style={{
              display: 'inline-block',
              background: 'var(--accent, #3b82f6)',
              color: '#fff',
              borderRadius: 6,
              padding: '7px 16px',
              fontSize: 13,
              fontWeight: 600,
              textDecoration: 'none',
            }}
          >
            Add Vendors in Settings
          </Link>
        </div>
      </div>
    );
  }

  if (data.reason === 'no_matches') {
    return (
      <div className="tab-page">
        <p style={{ color: '#2e7d32' }}>
          No known exploited vulnerabilities match your vendor stack.
        </p>
        {data.unmatched_vendors.length > 0 && (
          <p style={{ color: '#6b7280', fontSize: 13 }}>
            Vendors with no KEV matches: {data.unmatched_vendors.join(', ')}
          </p>
        )}
      </div>
    );
  }

  const { severity_breakdown: sb } = data;
  const totalPages = Math.ceil(data.total_matched / pageSize);

  return (
    <div className="tab-page">
      <div className="overview-toolbar">
        <button className="overview-refresh-btn" onClick={() => load(page)} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
        {data.kev_last_ingest_at && (
          <span className="overview-last-updated">
            KEV data as of: {new Date(data.kev_last_ingest_at).toLocaleDateString()}
          </span>
        )}
      </div>

      {/* Severity summary */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap', alignItems: 'center' }}>
        <strong>{data.total_matched} matched vulnerabilities</strong>
        {sb.critical > 0 && <span><SeverityBadge label="Critical" /> {sb.critical}</span>}
        {sb.high > 0 && <span><SeverityBadge label="High" /> {sb.high}</span>}
        {sb.medium > 0 && <span><SeverityBadge label="Medium" /> {sb.medium}</span>}
        {sb.low > 0 && <span><SeverityBadge label="Low" /> {sb.low}</span>}
        {sb.unknown > 0 && <span><SeverityBadge label="Unknown" /> {sb.unknown}</span>}
      </div>

      {data.unmatched_vendors.length > 0 && (
        <p style={{ color: '#6b7280', fontSize: 13, marginBottom: '0.75rem' }}>
          Vendors with no KEV matches: {data.unmatched_vendors.join(', ')}
        </p>
      )}

      {/* Full alerts table */}
      <div className="table-scroll-wrapper">
      <table className="tab-table">
        <thead>
          <tr style={{ borderBottom: '2px solid #e5e7eb', textAlign: 'left' }}>
            <th style={{ padding: '6px 8px' }}>CVE ID</th>
            <th style={{ padding: '6px 8px' }}>Vendor</th>
            <th style={{ padding: '6px 8px' }}>Product</th>
            <th style={{ padding: '6px 8px' }}>Severity</th>
            <th style={{ padding: '6px 8px' }}>CVSS</th>
            <th style={{ padding: '6px 8px' }}>Risk Score</th>
            <th style={{ padding: '6px 8px' }}>Date Added</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={`${item.cve_id}-${item.vendor_name}-${item.kev_product}`} style={{ borderBottom: '1px solid #f3f4f6' }}>
              <td style={{ padding: '6px 8px', fontFamily: 'monospace' }}>{item.cve_id}</td>
              <td style={{ padding: '6px 8px' }}>{item.vendor_name}</td>
              <td style={{ padding: '6px 8px' }}>{item.kev_product}</td>
              <td style={{ padding: '6px 8px' }}><SeverityBadge label={item.severity_label} /></td>
              <td style={{ padding: '6px 8px', fontWeight: 700 }}>
                {item.cvss_score !== null ? item.cvss_score.toFixed(1) : '—'}
              </td>
              <td style={{ padding: '6px 8px' }}>
                {item.risk_score !== null ? item.risk_score.toFixed(0) : '—'}
              </td>
              <td style={{ padding: '6px 8px' }}>
                {item.due_date ? new Date(item.due_date).toLocaleDateString() : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', marginTop: '0.75rem', justifyContent: 'center' }}>
          <button className="action-btn" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
            Previous
          </button>
          <span style={{ fontSize: 13 }}>Page {page} of {totalPages}</span>
          <button className="action-btn" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
            Next
          </button>
        </div>
      )}
    </div>
  );
};

export default VendorAlertsTab;
