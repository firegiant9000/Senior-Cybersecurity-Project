import React, { useEffect, useState } from 'react';
import { fetchVendorAlerts, VendorAlertsResponse } from '../../api/vendorAlerts';
import { useAuth } from '../../context/AuthContext';
import SeverityBadge from './SeverityBadge';
import InfoTip from './InfoTip';

export const VENDOR_ALERT_TIP =
  'A newly published CVE affecting one of your configured technology vendors. Each row links a known exploited vulnerability (KEV) to a vendor in your stack.';

const wrapperStyle: React.CSSProperties = { gridColumn: 'span 2' };

const Title: React.FC = () => (
  <span className="widget-title">
    Vendor Vulnerability Alerts
    <InfoTip text={VENDOR_ALERT_TIP} label="Vendor Vulnerability Alerts" />
  </span>
);

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
      <div className="card chart-widget" style={wrapperStyle}>
        <Title />
        <p style={{ padding: '1rem', color: 'var(--text-muted)' }}>Loading...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card chart-widget" style={wrapperStyle}>
        <Title />
        <p style={{ padding: '1rem', color: '#d32f2f' }}>{error}</p>
      </div>
    );
  }

  if (!data || data.reason === 'no_vendors') {
    return (
      <div className="card chart-widget" style={wrapperStyle}>
        <Title />
        <p style={{ padding: '1rem', color: 'var(--text-muted)' }}>
          Add your technology vendors in Settings to see matched vulnerability alerts.
        </p>
      </div>
    );
  }

  if (data.reason === 'no_matches') {
    return (
      <div className="card chart-widget" style={wrapperStyle}>
        <Title />
        <p style={{ padding: '1rem', color: '#2e7d32' }}>
          No known exploited vulnerabilities match your vendor stack.
        </p>
      </div>
    );
  }

  const { severity_breakdown: sb } = data;

  return (
    <div className="card chart-widget" style={wrapperStyle}>
      <Title />
      <div style={{ padding: '0.75rem 1rem' }}>
        {/* Severity breakdown bar */}
        <div className="vendor-alerts-card-summary">
          {sb.critical > 0 && (
            <span className="vendor-alerts-card-pill">
              <SeverityBadge label="Critical" /> <strong>{sb.critical}</strong>
            </span>
          )}
          {sb.high > 0 && (
            <span className="vendor-alerts-card-pill">
              <SeverityBadge label="High" /> <strong>{sb.high}</strong>
            </span>
          )}
          {sb.medium > 0 && (
            <span className="vendor-alerts-card-pill">
              <SeverityBadge label="Medium" /> <strong>{sb.medium}</strong>
            </span>
          )}
          {sb.low > 0 && (
            <span className="vendor-alerts-card-pill">
              <SeverityBadge label="Low" /> <strong>{sb.low}</strong>
            </span>
          )}
          {sb.unknown > 0 && (
            <span className="vendor-alerts-card-pill">
              <SeverityBadge label="Unknown" /> <strong>{sb.unknown}</strong>
            </span>
          )}
          <span className="vendor-alerts-card-total">{data.total_matched} total</span>
        </div>

        {/* Top alerts list */}
        <table className="vendor-alerts-card-table">
          <thead>
            <tr>
              <th>CVE</th>
              <th>Vendor</th>
              <th>Product</th>
              <th>Severity</th>
              <th>CVSS</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((item) => (
              <tr key={`${item.cve_id}-${item.vendor_name}-${item.kev_product}`}>
                <td className="vendor-alerts-card-cve">{item.cve_id}</td>
                <td>{item.vendor_name}</td>
                <td>{item.kev_product}</td>
                <td><SeverityBadge label={item.severity_label} /></td>
                <td className="vendor-alerts-card-cvss">
                  {item.cvss_score !== null ? item.cvss_score.toFixed(1) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {/* Footer */}
        <div className="vendor-alerts-card-footer">
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
