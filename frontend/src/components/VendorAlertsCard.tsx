import React, { useEffect, useState } from 'react';
import { fetchVendorAlerts, VendorAlertsResponse } from '../api/vendorAlerts';
import { useAuth } from '../context/AuthContext';
import SeverityBadge from './SeverityBadge';

const VendorAlertsCard: React.FC = () => {
  const { user } = useAuth();
  const [data, setData] = useState<VendorAlertsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!user) return;
    let cancelled = false;
    const load = async () => {
      try {
        const result = await fetchVendorAlerts(1, 5);
        if (!cancelled) setData(result);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load');
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [user]);

  if (loading) {
    return (
      <div className="card chart-widget" style={{ gridColumn: 'span 2' }}>
        <span className="widget-title">Vendor Vulnerability Alerts</span>
        <p style={{ padding: '1rem', color: '#6b7280' }}>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card chart-widget" style={{ gridColumn: 'span 2' }}>
        <span className="widget-title">Vendor Vulnerability Alerts</span>
        <p style={{ padding: '1rem', color: '#d32f2f' }}>{error}</p>
      </div>
    );
  }

  if (!data || data.reason === 'no_vendors') {
    return (
      <div className="card chart-widget" style={{ gridColumn: 'span 2' }}>
        <span className="widget-title">Vendor Vulnerability Alerts</span>
        <p style={{ padding: '1rem', color: '#6b7280' }}>
          Add your technology vendors in Settings to see matched vulnerability alerts.
        </p>
      </div>
    );
  }

  if (data.reason === 'no_matches') {
    return (
      <div className="card chart-widget" style={{ gridColumn: 'span 2' }}>
        <span className="widget-title">Vendor Vulnerability Alerts</span>
        <p style={{ padding: '1rem', color: '#2e7d32' }}>
          No known exploited vulnerabilities match your vendor stack.
        </p>
      </div>
    );
  }

  const { severity_breakdown: sb } = data;

  return (
    <div className="card chart-widget" style={{ gridColumn: 'span 2' }}>
      <span className="widget-title">Vendor Vulnerability Alerts</span>
      <div style={{ padding: '0.75rem 1rem' }}>
        {/* Severity breakdown bar */}
        <div style={{ display: 'flex', gap: '0.75rem', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
          {sb.critical > 0 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <SeverityBadge label="Critical" /> <strong>{sb.critical}</strong>
            </span>
          )}
          {sb.high > 0 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <SeverityBadge label="High" /> <strong>{sb.high}</strong>
            </span>
          )}
          {sb.medium > 0 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <SeverityBadge label="Medium" /> <strong>{sb.medium}</strong>
            </span>
          )}
          {sb.low > 0 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <SeverityBadge label="Low" /> <strong>{sb.low}</strong>
            </span>
          )}
          {sb.unknown > 0 && (
            <span style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <SeverityBadge label="Unknown" /> <strong>{sb.unknown}</strong>
            </span>
          )}
          <span style={{ color: '#6b7280', fontSize: 13, marginLeft: 'auto' }}>
            {data.total_matched} total
          </span>
        </div>

        {/* Top alerts list */}
        <table style={{ width: '100%', fontSize: 13, borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid #e5e7eb', textAlign: 'left' }}>
              <th style={{ padding: '4px 8px' }}>CVE</th>
              <th style={{ padding: '4px 8px' }}>Vendor</th>
              <th style={{ padding: '4px 8px' }}>Product</th>
              <th style={{ padding: '4px 8px' }}>Severity</th>
              <th style={{ padding: '4px 8px' }}>CVSS</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <tr key={`${item.cve_id}-${item.vendor_name}-${item.kev_product}`} style={{ borderBottom: '1px solid #f3f4f6' }}>
                <td style={{ padding: '4px 8px', fontFamily: 'monospace' }}>{item.cve_id}</td>
                <td style={{ padding: '4px 8px' }}>{item.vendor_name}</td>
                <td style={{ padding: '4px 8px' }}>{item.kev_product}</td>
                <td style={{ padding: '4px 8px' }}><SeverityBadge label={item.severity_label} /></td>
                <td style={{ padding: '4px 8px', fontWeight: 700 }}>
                  {item.cvss_score !== null ? item.cvss_score.toFixed(1) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Footer */}
        <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: '0.5rem', fontSize: 11, color: '#9ca3af' }}>
          {data.kev_last_ingest_at && (
            <span>KEV data as of: {new Date(data.kev_last_ingest_at).toLocaleDateString()}</span>
          )}
          {data.unmatched_vendors.length > 0 && (
            <span>{data.unmatched_vendors.length} vendor(s) had no KEV matches</span>
          )}
        </div>
      </div>
    </div>
  );
};

export default VendorAlertsCard;
