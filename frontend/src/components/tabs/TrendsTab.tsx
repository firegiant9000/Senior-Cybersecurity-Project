import React, { useMemo, useCallback, useEffect } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import { useTrendsData } from '../../hooks/useTrendsData';
import { useRefreshProgress } from '../../hooks/useRefreshProgress';
import RefreshButton from '../RefreshButton';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import { COLORS } from '../../theme';
import { IC3_SECTORS } from '../../api/tabsApi';

interface ProjectedPoint {
  year: number;
  projected_complaints: number | null;
  projected_loss:       number | null;
  projected_avg_loss:   number | null;
}

function projectLinear(
  items: Array<{ year: number; complaint_count: number; total_loss: number; avg_loss_per_incident: number }>,
  yearsAhead = 2,
): ProjectedPoint[] {
  const recent = items.slice(-Math.min(4, items.length));
  if (recent.length < 2) return [];
  const first = recent[0];
  const last  = recent[recent.length - 1];
  const span  = last.year - first.year;
  if (span === 0) return [];

  const slopes = {
    complaints: (last.complaint_count       - first.complaint_count)       / span,
    loss:       (last.total_loss            - first.total_loss)            / span,
    avg:        (last.avg_loss_per_incident - first.avg_loss_per_incident) / span,
  };

  return Array.from({ length: yearsAhead }, (_, i) => ({
    year:                 last.year + i + 1,
    projected_complaints: Math.max(0, Math.round(last.complaint_count       + slopes.complaints * (i + 1))),
    projected_loss:       Math.max(0, last.total_loss            + slopes.loss       * (i + 1)),
    projected_avg_loss:   Math.max(0, last.avg_loss_per_incident + slopes.avg        * (i + 1)),
  }));
}

function trendLegend({ payload }: { payload?: ReadonlyArray<{ value?: string; color?: string }> }) {
  const sorted = [...(payload ?? [])].sort((a, b) =>
    a.value === 'Projected' ? 1 : b.value === 'Projected' ? -1 : 0
  );
  return (
    <div className="trends-legend">
      {sorted.map((entry, i) => (
        <span key={i} className="trends-legend-item">
          <svg width="28" height="12">
            {entry.value === 'Projected' ? (
              <line x1="2" y1="6" x2="26" y2="6" stroke={entry.color} strokeWidth="2" strokeDasharray="8 4" strokeOpacity="0.5" />
            ) : (
              <line x1="2" y1="6" x2="26" y2="6" stroke={entry.color} strokeWidth="3" />
            )}
          </svg>
          {entry.value}
        </span>
      ))}
    </div>
  );
}

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
  const { data, loading, errors, setAttackType, setSector, setYearFrom, setYearTo, refresh, setOnProgress } = useTrendsData();
  const { trends, attackTypeOptions, selectedAttackType, selectedSector, yearFrom, yearTo } = data;
  const progressState = useRefreshProgress();

  // Register progress callback
  useEffect(() => {
    setOnProgress?.(progressState.markItemComplete);
  }, [setOnProgress, progressState.markItemComplete]);

  // Reset progress when loading completes
  useEffect(() => {
    if (!loading && progressState.isActive) {
      progressState.reset();
    }
  }, [loading, progressState.reset, progressState.isActive]);

  const handleRefresh = useCallback(() => {
    progressState.start(['Trends data']);
    refresh();
  }, [refresh, progressState.start]);

  const projected = useMemo(() => projectLinear(trends), [trends]);

  const chartData = useMemo(() => {
    const map = new Map<number, Record<string, number | null>>();
    for (const d of trends) {
      map.set(d.year, {
        complaint_count:       d.complaint_count,
        total_loss:            d.total_loss,
        avg_loss_per_incident: d.avg_loss_per_incident,
        projected_complaints:  null,
        projected_loss:        null,
        projected_avg_loss:    null,
      });
    }
    // Bridge: copy actual values into projected keys at the last historical point
    // so the dashed line starts from where the solid line ends (no gap).
    if (trends.length > 0 && projected.length > 0) {
      const last = trends[trends.length - 1];
      const entry = map.get(last.year);
      if (entry) {
        entry.projected_complaints = last.complaint_count;
        entry.projected_loss       = last.total_loss;
        entry.projected_avg_loss   = last.avg_loss_per_incident;
      }
    }
    for (const p of projected) {
      map.set(p.year, {
        complaint_count:       null,
        total_loss:            null,
        avg_loss_per_incident: null,
        projected_complaints:  p.projected_complaints,
        projected_loss:        p.projected_loss,
        projected_avg_loss:    p.projected_avg_loss,
      });
    }
    return Array.from(map.entries())
      .sort(([a], [b]) => a - b)
      .map(([year, v]) => ({ year, ...v }));
  }, [trends, projected]);

  return (
    <div className="tab-page">
      <div className="overview-toolbar">
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
          <label htmlFor="sector-filter" style={{ fontSize: 13, color: '#555' }}>
            Sector:
          </label>
          <select
            id="sector-filter"
            className="trends-select"
            value={selectedSector ?? ''}
            onChange={e => setSector(e.target.value || undefined)}
          >
            <option value="">All sectors</option>
            {IC3_SECTORS.map(s => (
              <option key={s} value={s}>{s}</option>
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
        <div className="overview-toolbar-actions">
          <RefreshButton
            onClick={handleRefresh}
            loading={loading}
            items={progressState.items}
            progress={progressState.progress}
            label="Refresh"
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
              {selectedAttackType && <span className="widget-title-filter"> — {selectedAttackType}</span>}{selectedSector && <span className="widget-title-filter"> · {selectedSector}</span>}
            </span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : trends.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={fmtK} tick={{ fontSize: 11 }} width={52} />
                    <Tooltip
                      formatter={(v: unknown) => [
                        v == null ? '—' : typeof v === 'number' ? v.toLocaleString() : String(v),
                        'Complaints',
                      ]}
                    />
                    <Legend content={trendLegend} />
                    <Line
                      type="monotone"
                      dataKey="complaint_count"
                      name="Complaints"
                      stroke={COLORS.teal}
                      strokeWidth={4}
                      dot={{ r: 6 }}
                      activeDot={{ r: 8 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="projected_complaints"
                      name="Projected"
                      stroke={COLORS.teal}
                      strokeWidth={2}
                      strokeDasharray="10 5"
                      strokeOpacity={0.5}
                      dot={false}
                      connectNulls={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
            {projected.length > 0 && (
              <p className="trends-projection-note">
                Dashed = {projected[0].year}–{projected[projected.length - 1].year} projection · linear extrapolation from last {Math.min(4, trends.length)}-yr trend · not a predictive model
              </p>
            )}
          </div>
        </WidgetErrorBoundary>

        {/* Financial Loss */}
        <WidgetErrorBoundary title="Financial Loss Trend">
          <div className="card chart-widget trends-chart">
            <span className="widget-title">
              Total Financial Loss Over Time
              {selectedAttackType && <span className="widget-title-filter"> — {selectedAttackType}</span>}{selectedSector && <span className="widget-title-filter"> · {selectedSector}</span>}
            </span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : trends.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={fmtBillion} tick={{ fontSize: 11 }} width={64} />
                    <Tooltip
                      formatter={(v: unknown) => [
                        v == null ? '—' : `$${(v as number).toLocaleString()}`,
                        'Total Loss',
                      ]}
                    />
                    <Legend content={trendLegend} />
                    <Line
                      type="monotone"
                      dataKey="total_loss"
                      name="Total Loss"
                      stroke={COLORS.red}
                      strokeWidth={4}
                      dot={{ r: 6 }}
                      activeDot={{ r: 8 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="projected_loss"
                      name="Projected"
                      stroke={COLORS.red}
                      strokeWidth={2}
                      strokeDasharray="10 5"
                      strokeOpacity={0.5}
                      dot={false}
                      connectNulls={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
            {projected.length > 0 && (
              <p className="trends-projection-note">
                Dashed = {projected[0].year}–{projected[projected.length - 1].year} projection · linear extrapolation from last {Math.min(4, trends.length)}-yr trend · not a predictive model
              </p>
            )}
          </div>
        </WidgetErrorBoundary>

        {/* Avg Loss per Incident */}
        <WidgetErrorBoundary title="Avg Loss Per Incident">
          <div className="card chart-widget trends-chart">
            <span className="widget-title">
              Average Loss per Incident
              {selectedAttackType && <span className="widget-title-filter"> — {selectedAttackType}</span>}{selectedSector && <span className="widget-title-filter"> · {selectedSector}</span>}
            </span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : trends.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartData} margin={{ top: 8, right: 24, left: 0, bottom: 4 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="year" tick={{ fontSize: 11 }} />
                    <YAxis tickFormatter={fmtBillion} tick={{ fontSize: 11 }} width={64} />
                    <Tooltip
                      formatter={(v: unknown) => [
                        v == null ? '—' : `$${(v as number).toLocaleString()}`,
                        'Avg Loss / Incident',
                      ]}
                    />
                    <Legend content={trendLegend} />
                    <Line
                      type="monotone"
                      dataKey="avg_loss_per_incident"
                      name="Avg Loss / Incident"
                      stroke={COLORS.purple}
                      strokeWidth={4}
                      dot={{ r: 6 }}
                      activeDot={{ r: 8 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="projected_avg_loss"
                      name="Projected"
                      stroke={COLORS.purple}
                      strokeWidth={2}
                      strokeDasharray="10 5"
                      strokeOpacity={0.5}
                      dot={false}
                      connectNulls={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
            {projected.length > 0 && (
              <p className="trends-projection-note">
                Dashed = {projected[0].year}–{projected[projected.length - 1].year} projection · linear extrapolation from last {Math.min(4, trends.length)}-yr trend · not a predictive model
              </p>
            )}
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
