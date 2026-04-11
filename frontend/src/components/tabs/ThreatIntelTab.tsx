import React, { useMemo } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList,
  LineChart, Line, PieChart, Pie, Cell, Legend,
} from 'recharts';
import { useThreatIntelData } from '../../hooks/useThreatIntelData';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import { COLORS, RISK_COLORS, SEVERITY_COLORS } from '../../theme';

const SEVERITY_ORDER = ['Critical', 'High', 'Medium', 'Low', 'Unknown'];

function fmtM(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)     return `${Math.round(v / 1_000)}k`;
  return String(v);
}

function severityBadge(label: string) {
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

const ThreatIntelTab: React.FC = () => {
  const { data, loading, errors, refresh } = useThreatIntelData();

  // Aggregate top vendors from KEV data
  const topVendors = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const entry of data.recentKev) {
      const vendor = entry.vendor ?? 'Unknown';
      counts[vendor] = (counts[vendor] ?? 0) + 1;
    }
    return Object.entries(counts)
      .map(([vendor, count]) => ({ vendor, count }))
      .sort((a, b) => b.count - a.count)
      .slice(0, 10);
  }, [data.recentKev]);

  const sortedSeverity = useMemo(() => {
    return [...data.severityDistribution].sort(
      (a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity)
    );
  }, [data.severityDistribution]);

  return (
    <div className="tab-page">
      {/* Toolbar */}
      <div className="overview-toolbar">
        <button className="overview-refresh-btn" onClick={refresh}>↻ Refresh</button>
      </div>

      {errors.length > 0 && (
        <div className="overview-partial-errors">
          ⚠ Some widgets failed to load: {errors.join(' · ')}
        </div>
      )}

      <div className="threat-intel-grid">
        {/* CVE Publication Timeline */}
        <WidgetErrorBoundary title="CVE Timeline">
          <div className="card chart-widget ti-timeline">
            <span className="widget-title">CVE Publications by Year</span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : data.nvdTimeline.length === 0 ? (
                <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.nvdTimeline} margin={{ top: 8, right: 24, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={fmtM} tick={{ fontSize: 11 }} width={48} />
                    <Tooltip formatter={(v: unknown) => [(v as number).toLocaleString(), 'CVEs']} />
                    <Line
                      type="monotone"
                      dataKey="count"
                      stroke={COLORS.teal}
                      strokeWidth={2}
                      dot={{ r: 3 }}
                      activeDot={{ r: 5 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Severity Distribution donut */}
        <WidgetErrorBoundary title="Severity Distribution">
          <div className="card chart-widget ti-severity">
            <span className="widget-title">CVE Severity Distribution</span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : sortedSeverity.length === 0 ? (
                <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie
                      data={sortedSeverity}
                      dataKey="count"
                      nameKey="severity"
                      cx="50%"
                      cy="50%"
                      innerRadius="40%"
                      outerRadius="65%"
                      paddingAngle={2}
                    >
                      {sortedSeverity.map((entry) => (
                        <Cell
                          key={entry.severity}
                          fill={SEVERITY_COLORS[entry.severity as keyof typeof SEVERITY_COLORS] ?? '#9e9e9e'}
                        />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: unknown) => [(v as number).toLocaleString(), 'CVEs']} />
                    <Legend
                      iconType="circle"
                      iconSize={10}
                      formatter={(value: string) => (
                        <span style={{ fontSize: 12 }}>{value}</span>
                      )}
                    />
                  </PieChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Top Affected Vendors */}
        <WidgetErrorBoundary title="Top Affected Vendors">
          <div className="card chart-widget ti-vendors">
            <span className="widget-title">Top Affected Vendors (KEV)</span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : topVendors.length === 0 ? (
                <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topVendors}
                    layout="vertical"
                    margin={{ top: 4, right: 48, left: 4, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="vendor" width={120} tick={{ fontSize: 10 }} />
                    <Tooltip formatter={(v: unknown) => [(v as number), 'KEV entries']} />
                    <Bar dataKey="count" fill={COLORS.navy} radius={[0, 4, 4, 0]}>
                      <LabelList
                        dataKey="count"
                        position="right"
                        style={{ fontSize: 10, fill: '#555', fontWeight: 600 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Recent KEV Additions table */}
        <WidgetErrorBoundary title="Recent KEV Additions">
          <div className="card ti-kev-table">
            <span className="widget-title">Recent CISA KEV Additions</span>
            <div className="tab-table-scroll">
              {loading ? <WidgetSkeleton variant="chart" /> : data.recentKev.length === 0 ? (
                <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>
              ) : (
                <table className="tab-table">
                  <thead>
                    <tr>
                      <th>CVE ID</th>
                      <th>Vulnerability</th>
                      <th>Vendor</th>
                      <th>Severity</th>
                      <th>Date Added</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.recentKev.slice(0, 20).map(entry => (
                      <tr key={entry.id}>
                        <td><code style={{ fontSize: 11 }}>{entry.id}</code></td>
                        <td style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                            title={entry.vulnerability_name}>
                          {entry.vulnerability_name}
                        </td>
                        <td>{entry.vendor ?? '—'}</td>
                        <td>{severityBadge(entry.severity_label)}</td>
                        <td style={{ whiteSpace: 'nowrap' }}>{entry.kev_date_added ?? '—'}</td>
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

export default ThreatIntelTab;
