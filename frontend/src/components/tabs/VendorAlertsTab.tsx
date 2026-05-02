import React, { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { fetchVendorAlerts, VendorAlertsResponse } from '../../api/vendorAlerts';
import { createVendor, suggestVendors, type VendorSuggestion } from '../../api/vendors';
import { useAuth } from '../../context/AuthContext';
import SeverityBadge from '../shared/SeverityBadge';
import InfoTip from '../shared/InfoTip';
import './VendorAlertsTab.css';

const VENDOR_ALERT_TIP =
  'A newly published CVE affecting one of the technology vendors in your stack. Each row links a known exploited vulnerability (KEV) to a vendor you use.';
const SEVERITY_TIP =
  'Critical (CVSS 9.0–10.0), High (7.0–8.9), Medium (4.0–6.9), Low (0.1–3.9). Higher = more urgent to patch.';
const RISK_SCORE_TIP =
  '0–100 composite combining severity, KEV presence, exploitation probability, and recency. Higher = more risk.';

const VendorAlertsTab: React.FC = () => {
  const { user, orgId } = useAuth();
  const [data, setData] = useState<VendorAlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [suggestions, setSuggestions] = useState<Record<string, VendorSuggestion[]>>({});
  const [adding, setAdding] = useState<Record<string, 'pending' | 'added' | 'error'>>({});
  const pageSize = 20;

  const handleAddVendor = async (vendorName: string, productName?: string) => {
    if (!orgId) return;
    setAdding((m) => ({ ...m, [vendorName]: 'pending' }));
    try {
      await createVendor(orgId, vendorName, productName ?? '');
      setAdding((m) => ({ ...m, [vendorName]: 'added' }));
      load(page);
    } catch {
      setAdding((m) => ({ ...m, [vendorName]: 'error' }));
    }
  };

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

  useEffect(() => {
    if (!data?.unmatched_vendors?.length) return;
    const toCheck = data.unmatched_vendors.slice(0, 5);
    let cancelled = false;
    Promise.all(
      toCheck.map(v => suggestVendors(v).then(s => [v, s] as [string, VendorSuggestion[]]).catch(() => [v, []] as [string, VendorSuggestion[]]))
    ).then(pairs => {
      if (cancelled) return;
      setSuggestions(Object.fromEntries(pairs));
    });
    return () => { cancelled = true; };
  }, [data?.unmatched_vendors]);

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
          <p style={{ fontSize: 13, color: 'var(--text-secondary, #555)', marginBottom: 16 }}>
            Add your technology stack in Organization Profile. We'll match your vendors against the CISA Known Exploited Vulnerabilities catalog and alert you to active threats.
          </p>
          <Link
            to="/org-profile#section-vendors"
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
            Add Vendors in Technology Stack
          </Link>
        </div>
      </div>
    );
  }

  if (data.reason === 'no_matches') {
    return (
      <div className="tab-page">
        <div className="overview-toolbar" style={{ marginBottom: '1rem' }}>
          <Link to="/org-profile#section-vendors" style={{ fontSize: 13, color: 'var(--accent)', textDecoration: 'underline' }}>
            Manage Vendors →
          </Link>
        </div>
        <div className="vendor-no-matches-card">
          <span className="vendor-no-matches-icon">✅</span>
          <p className="vendor-no-matches-title">No active threats for your stack</p>
          <p className="vendor-no-matches-sub">
            None of your vendors appear in CISA's Known Exploited Vulnerabilities catalog right now. Check back after the next data refresh.
          </p>
          {data.unmatched_vendors.length > 0 && (
            <div className="vendor-unmatched-list">
              <p className="vendor-unmatched-heading">Unmatched vendors (not found in KEV catalog):</p>
              {data.unmatched_vendors.slice(0, 5).map(v => {
                const hits = suggestions[v];
                return (
                  <div key={v} className="vendor-unmatched-row">
                    <span className="vendor-unmatched-name">{v}</span>
                    {hits && hits.length > 0
                      ? <span className="vendor-unmatched-suggestion">
                          — Did you mean: {hits.map((s, i) => {
                            const state = adding[s.vendor_name];
                            return (
                              <span key={s.vendor_name}>
                                {i > 0 && ', '}
                                <strong>{s.vendor_name}</strong> ({Math.round(s.score * 100)}%)
                                {state === 'added'
                                  ? <span className="vendor-add-btn vendor-add-btn--done"> ✓ Added</span>
                                  : (
                                    <button
                                      className="vendor-add-btn"
                                      disabled={state === 'pending' || !orgId}
                                      onClick={() => handleAddVendor(s.vendor_name)}
                                    >
                                      {state === 'pending' ? 'Adding…' : state === 'error' ? 'Retry' : '+ Add'}
                                    </button>
                                  )}
                              </span>
                            );
                          })}?
                        </span>
                      : <span className="vendor-unmatched-none">— not in KEV catalog</span>
                    }
                  </div>
                );
              })}
              {data.unmatched_vendors.length > 5 && (
                <p className="vendor-unmatched-more">+{data.unmatched_vendors.length - 5} more</p>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  const { severity_breakdown: sb } = data;
  const totalPages = Math.ceil(data.total_matched / pageSize);

  return (
    <div className="tab-page">
      <h2 style={{ margin: '0 0 0.75rem', fontSize: 18, fontWeight: 700 }}>
        Vendor Alerts
        <InfoTip text={VENDOR_ALERT_TIP} label="Vendor Alerts" />
      </h2>
      <div className="overview-toolbar">
        <button className="overview-refresh-btn" onClick={() => load(page)} disabled={loading}>
          {loading ? 'Refreshing...' : 'Refresh'}
        </button>
        <Link to="/org-profile#section-vendors" style={{ fontSize: 13, color: 'var(--accent)', textDecoration: 'underline' }}>
          Manage Vendors →
        </Link>
        {data.kev_last_ingest_at && (
          <span className="overview-last-updated">
            KEV<InfoTip text="Known Exploited Vulnerabilities — CISA's catalog of CVEs actively being exploited." /> data as of: {new Date(data.kev_last_ingest_at).toLocaleDateString()}
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
        <div className="vendor-unmatched-list vendor-unmatched-list--inline">
          {data.unmatched_vendors.slice(0, 5).map(v => {
            const hits = suggestions[v];
            return (
              <div key={v} className="vendor-unmatched-row">
                <span className="vendor-unmatched-name">{v}</span>
                {hits && hits.length > 0
                  ? <span className="vendor-unmatched-suggestion">
                      — Did you mean: {hits.map((s, i) => (
                        <span key={s.vendor_name}>
                          {i > 0 && ', '}
                          <strong>{s.vendor_name}</strong> ({Math.round(s.score * 100)}%)
                        </span>
                      ))}?
                    </span>
                  : <span className="vendor-unmatched-none">— no KEV match</span>
                }
              </div>
            );
          })}
          {data.unmatched_vendors.length > 5 && (
            <p className="vendor-unmatched-more">+{data.unmatched_vendors.length - 5} more unmatched</p>
          )}
        </div>
      )}

      {/* Full alerts table */}
      <div className="table-scroll-wrapper">
      <table className="tab-table">
        <thead>
          <tr style={{ borderBottom: '2px solid var(--border)', textAlign: 'left' }}>
            <th style={{ padding: '6px 8px' }}>CVE ID<InfoTip text="CVE (Common Vulnerabilities and Exposures) — a unique ID for a known security flaw" /></th>
            <th style={{ padding: '6px 8px' }}>Vendor</th>
            <th style={{ padding: '6px 8px' }}>Product</th>
            <th style={{ padding: '6px 8px' }}>Severity<InfoTip text={SEVERITY_TIP} label="Severity" /></th>
            <th style={{ padding: '6px 8px' }}>CVSS<InfoTip text="CVSS (Common Vulnerability Scoring System) — severity score from 0–10" /></th>
            <th style={{ padding: '6px 8px' }}>Risk Score<InfoTip text={RISK_SCORE_TIP} label="Risk Score" /></th>
            <th style={{ padding: '6px 8px' }}>Date Added</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((item) => (
            <tr key={`${item.cve_id}-${item.vendor_name}-${item.kev_product}`} style={{ borderBottom: '1px solid var(--border)' }}>
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
