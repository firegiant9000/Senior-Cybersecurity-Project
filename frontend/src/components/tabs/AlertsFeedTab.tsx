import React from 'react';
import { useAlertsData } from '../../hooks/useAlertsData';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import { RISK_COLORS } from '../../theme';

function SeverityBadge({ label }: { label: string }) {
  const color = RISK_COLORS[label as keyof typeof RISK_COLORS] ?? '#9e9e9e';
  return (
    <span
      style={{
        background: color,
        color: '#fff',
        borderRadius: 3,
        padding: '1px 6px',
        fontSize: 11,
        fontWeight: 700,
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </span>
  );
}

function ScorePill({ score }: { score: number | null }) {
  if (score === null) return <span style={{ color: 'var(--text-muted, #6b7280)' }}>—</span>;
  const color = score >= 9 ? '#d32f2f' : score >= 7 ? '#e65100' : score >= 4 ? '#00bcd4' : '#2e7d32';
  return (
    <span style={{ color, fontWeight: 700, fontSize: 13 }}>
      {score.toFixed(1)}
    </span>
  );
}

const AlertsFeedTab: React.FC = () => {
  const { data, loading, errors, refresh } = useAlertsData();

  return (
    <div className="tab-page">
      <div className="overview-toolbar">
        <button className="overview-refresh-btn" onClick={refresh}>↻ Refresh</button>
        <span className="overview-last-updated" style={{ color: '#d32f2f', fontWeight: 600 }}>
          ● Live Feed
        </span>
      </div>

      {errors.length > 0 && (
        <div className="overview-partial-errors">
          ⚠ Some feeds failed: {errors.join(' · ')}
        </div>
      )}

      <div className="alerts-grid">
        {/* CISA KEV Recent Additions */}
        <WidgetErrorBoundary title="CISA KEV Alerts">
          <div className="card alerts-card">
            <span className="widget-title">
              🔴 CISA Known Exploited Vulnerabilities — Most Recent
            </span>
            <div className="tab-table-scroll">
              {loading ? <WidgetSkeleton variant="chart" /> : data.recentKev.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <table className="tab-table">
                  <thead>
                    <tr>
                      <th>CVE ID</th>
                      <th>Vulnerability</th>
                      <th>Vendor / Product</th>
                      <th>Severity</th>
                      <th>CVSS</th>
                      <th>Date Added</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recentKev.map(entry => (
                      <tr key={entry.id}>
                        <td><code style={{ fontSize: 11 }}>{entry.id}</code></td>
                        <td
                          style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          title={entry.vulnerability_name}
                        >
                          {entry.vulnerability_name}
                        </td>
                        <td style={{ whiteSpace: 'nowrap' }}>
                          {entry.vendor ?? '—'}
                          {entry.product ? ` / ${entry.product}` : ''}
                        </td>
                        <td><SeverityBadge label={entry.severity_label} /></td>
                        <td><ScorePill score={entry.severity_score} /></td>
                        <td style={{ whiteSpace: 'nowrap' }}>{entry.kev_date_added ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Recent NVD CVEs */}
        <WidgetErrorBoundary title="Recent NVD CVEs">
          <div className="card alerts-card">
            <span className="widget-title">
              🔵 Recently Published NVD CVEs
            </span>
            <div className="tab-table-scroll">
              {loading ? <WidgetSkeleton variant="chart" /> : data.recentCves.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <table className="tab-table">
                  <thead>
                    <tr>
                      <th>CVE ID</th>
                      <th>Description</th>
                      <th>Severity</th>
                      <th>CVSS</th>
                      <th>Published</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recentCves.map(cve => (
                      <tr key={cve.id}>
                        <td><code style={{ fontSize: 11 }}>{cve.id}</code></td>
                        <td
                          style={{ maxWidth: 280, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                          title={cve.description}
                        >
                          {cve.description}
                        </td>
                        <td><SeverityBadge label={cve.severity_label} /></td>
                        <td><ScorePill score={cve.severity_score} /></td>
                        <td style={{ whiteSpace: 'nowrap' }}>{cve.published_date ?? '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>
      </div>
    </div>
  );
};

export default AlertsFeedTab;
