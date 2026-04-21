import React from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { useTrendsData } from '../../hooks/useTrendsData';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import { COLORS } from '../../theme';

function fmtBillion(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000)     return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)         return `$${Math.round(v / 1_000)}k`;
  return `$${v}`;
}

function fmtK(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)     return `${Math.round(v / 1_000)}k`;
  return String(v);
}

const TrendsTab: React.FC = () => {
  const { data, loading, errors, setAttackType, setYearFrom, setYearTo, refresh } = useTrendsData();
  const { trends, attackTypeOptions, selectedAttackType, yearFrom, yearTo } = data;

  return (
    <div className="tab-page">
      <div className="overview-toolbar">
        <button className="overview-refresh-btn" onClick={refresh}>↻ Refresh</button>
        <div className="trends-filter">
          <label htmlFor="attack-type-filter" style={{ fontSize: 13, color: '#555' }}>
            Attack type:
          </label>
          <select
            id="attack-type-filter"
            className="trends-select"
            value={selectedAttackType ?? ''}
            onChange={e => setAttackType(e.target.value || undefined)}
          >
            <option value="">All attack types</option>
            {attackTypeOptions.map(t => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
        </div>
        <div className="trends-filter">
          <label htmlFor="year-from-filter" style={{ fontSize: 13, color: '#555' }}>
            Year from:
          </label>
          <input
            id="year-from-filter"
            type="number"
            className="trends-year-input"
            min={2000}
            max={new Date().getFullYear()}
            placeholder="e.g. 2018"
            value={yearFrom ?? ''}
            onChange={e => setYearFrom(e.target.value ? Number(e.target.value) : undefined)}
          />
        </div>
        <div className="trends-filter">
          <label htmlFor="year-to-filter" style={{ fontSize: 13, color: '#555' }}>
            Year to:
          </label>
          <input
            id="year-to-filter"
            type="number"
            className="trends-year-input"
            min={2000}
            max={new Date().getFullYear()}
            placeholder={String(new Date().getFullYear())}
            value={yearTo ?? ''}
            onChange={e => setYearTo(e.target.value ? Number(e.target.value) : undefined)}
          />
        </div>
      </div>

      {errors.length > 0 && (
        <div className="overview-partial-errors">
          ⚠ {errors.join(' · ')}
        </div>
      )}

      <div className="trends-grid">
        {/* Complaint Volume */}
        <WidgetErrorBoundary title="Complaint Volume Trend">
          <div className="card chart-widget trends-chart">
            <span className="widget-title">
              IC3 Complaint Volume Over Time
              {selectedAttackType && <span className="widget-title-filter"> — {selectedAttackType}</span>}
            </span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : trends.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trends} margin={{ top: 8, right: 24, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={fmtK} tick={{ fontSize: 11 }} width={52} />
                    <Tooltip
                      formatter={(v: unknown) => [(v as number).toLocaleString(), 'Complaints']}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="complaint_count"
                      name="Complaints"
                      stroke={COLORS.teal}
                      strokeWidth={4}
                      dot={{ r: 6 }}
                      activeDot={{ r: 8 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Financial Loss */}
        <WidgetErrorBoundary title="Financial Loss Trend">
          <div className="card chart-widget trends-chart">
            <span className="widget-title">
              Total Financial Loss Over Time
              {selectedAttackType && <span className="widget-title-filter"> — {selectedAttackType}</span>}
            </span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : trends.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trends} margin={{ top: 8, right: 24, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={fmtBillion} tick={{ fontSize: 11 }} width={64} />
                    <Tooltip
                      formatter={(v: unknown) => [
                        `$${(v as number).toLocaleString()}`,
                        'Total Loss',
                      ]}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="total_loss"
                      name="Total Loss"
                      stroke={COLORS.red}
                      strokeWidth={4}
                      dot={{ r: 6 }}
                      activeDot={{ r: 8 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Avg Loss per Incident */}
        <WidgetErrorBoundary title="Avg Loss Per Incident">
          <div className="card chart-widget trends-chart">
            <span className="widget-title">
              Average Loss per Incident
              {selectedAttackType && <span className="widget-title-filter"> — {selectedAttackType}</span>}
            </span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : trends.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trends} margin={{ top: 8, right: 24, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={fmtBillion} tick={{ fontSize: 11 }} width={64} />
                    <Tooltip
                      formatter={(v: unknown) => [
                        `$${(v as number).toLocaleString()}`,
                        'Avg Loss / Incident',
                      ]}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="avg_loss_per_incident"
                      name="Avg Loss / Incident"
                      stroke={COLORS.purple}
                      strokeWidth={4}
                      dot={{ r: 6 }}
                      activeDot={{ r: 8 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Data summary table */}
        <WidgetErrorBoundary title="Trends Data Table">
          <div className="card trends-table-card">
            <span className="widget-title">Year-by-Year Summary</span>
            <div className="tab-table-scroll">
              {loading ? <WidgetSkeleton variant="chart" /> : trends.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <table className="tab-table">
                  <thead>
                    <tr>
                      <th>Year</th>
                      <th>Complaints</th>
                      <th>Total Loss</th>
                      <th>Avg Loss / Incident</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...trends].reverse().map(row => (
                      <tr key={row.year}>
                        <td><strong>{row.year}</strong></td>
                        <td>{row.complaint_count.toLocaleString()}</td>
                        <td>${row.total_loss.toLocaleString()}</td>
                        <td>${row.avg_loss_per_incident.toLocaleString()}</td>
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

export default TrendsTab;
