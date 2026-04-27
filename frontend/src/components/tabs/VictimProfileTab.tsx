import React, { useCallback, useEffect, useRef } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList,
} from 'recharts';
import { useVictimData } from '../../hooks/useVictimData';
import { useRefreshProgress } from '../../hooks/useRefreshProgress';
import RefreshButton from '../RefreshButton';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import { COLORS } from '../../theme';

function fmtMoney(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000)     return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)         return `$${Math.round(v / 1_000)}k`;
  return `$${v}`;
}

function truncate(str: string, max = 22): string {
  return str.length > max ? str.slice(0, max) + '…' : str;
}

const VictimProfileTab: React.FC = () => {
  const { data, loading, errors, refresh, setOnProgress } = useVictimData();
  const progressState = useRefreshProgress();
  const { markItemComplete, reset, start, isActive } = progressState;
  const wasLoadingRef = useRef(loading);

  // Register progress callback
  useEffect(() => {
    setOnProgress?.(markItemComplete);
  }, [setOnProgress, markItemComplete]);

  // Reset progress when loading completes
  useEffect(() => {
    if (wasLoadingRef.current && !loading && isActive) {
      reset();
    }
    wasLoadingRef.current = loading;
  }, [loading, reset, isActive]);

  const handleRefresh = useCallback(() => {
    start(['Attack types', 'Industry risk']);
    refresh();
  }, [refresh, start]);

  const topLossByAttack = [...data.attackTypes]
    .sort((a, b) => b.total_loss - a.total_loss)
    .slice(0, 10)
    .map(d => ({ ...d, label: truncate(d.attack_type) }));

  const topAvgLossBySector = [...data.industryRisk]
    .sort((a, b) => b.avg_loss_per_incident - a.avg_loss_per_incident)
    .slice(0, 10)
    .map(d => ({ ...d, label: truncate(d.sector) }));

  const topComplaintsBySector = [...data.industryRisk]
    .sort((a, b) => b.complaint_count - a.complaint_count)
    .slice(0, 10)
    .map(d => ({ ...d, label: truncate(d.sector) }));

  return (
    <div className="tab-page">
      <div className="overview-toolbar">
        <RefreshButton
          onClick={handleRefresh}
          loading={loading}
          items={progressState.items}
          progress={progressState.progress}
          label="Refresh"
        />
        <span style={{ fontSize: 12, color: 'var(--text-muted, #6b7280)' }}>
          Based on IC3 complaint data — no individual victim data is stored.
        </span>
      </div>

      {errors.length > 0 && (
        <div className="overview-partial-errors">
          ⚠ Some widgets failed: {errors.join(' · ')}
        </div>
      )}

      <div className="victim-grid">
        {/* Total Financial Loss by Attack Type */}
        <WidgetErrorBoundary title="Loss by Attack Type">
          <div className="card chart-widget victim-chart">
            <span className="widget-title">Total Financial Loss by Attack Type</span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : topLossByAttack.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topLossByAttack}
                    layout="vertical"
                    margin={{ top: 4, right: 72, left: 4, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tickFormatter={fmtMoney} tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="label" width={160} tick={{ fontSize: 10 }} />
                    <Tooltip
                      formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, 'Total Loss']}
                      labelFormatter={(label: unknown) => {
                        const match = topLossByAttack.find(d => d.label === label);
                        return match?.attack_type ?? String(label);
                      }}
                    />
                    <Bar dataKey="total_loss" fill={COLORS.red} radius={[0, 4, 4, 0]}>
                      <LabelList
                        dataKey="total_loss"
                        position="right"
                        formatter={(v: unknown) => fmtMoney(v as number)}
                        style={{ fontSize: 10, fill: '#555', fontWeight: 600 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Avg Loss per Incident by Sector */}
        <WidgetErrorBoundary title="Avg Loss by Sector">
          <div className="card chart-widget victim-chart">
            <span className="widget-title">Average Loss per Incident by Sector</span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : topAvgLossBySector.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topAvgLossBySector}
                    layout="vertical"
                    margin={{ top: 4, right: 72, left: 4, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tickFormatter={fmtMoney} tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 10 }} />
                    <Tooltip
                      formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, 'Avg Loss']}
                      labelFormatter={(label: unknown) => {
                        const match = topAvgLossBySector.find(d => d.label === label);
                        return match?.sector ?? String(label);
                      }}
                    />
                    <Bar dataKey="avg_loss_per_incident" fill={COLORS.navy} radius={[0, 4, 4, 0]}>
                      <LabelList
                        dataKey="avg_loss_per_incident"
                        position="right"
                        formatter={(v: unknown) => fmtMoney(v as number)}
                        style={{ fontSize: 10, fill: '#555', fontWeight: 600 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Complaint Count by Sector */}
        <WidgetErrorBoundary title="Complaints by Sector">
          <div className="card chart-widget victim-chart">
            <span className="widget-title">Complaint Count by Sector</span>
            <div className="chart-body">
              {loading ? <WidgetSkeleton variant="chart" /> : topComplaintsBySector.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={topComplaintsBySector}
                    layout="vertical"
                    margin={{ top: 4, right: 64, left: 4, bottom: 4 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" tick={{ fontSize: 10 }} />
                    <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 10 }} />
                    <Tooltip
                      formatter={(v: unknown) => [(v as number).toLocaleString(), 'Complaints']}
                      labelFormatter={(label: unknown) => {
                        const match = topComplaintsBySector.find(d => d.label === label);
                        return match?.sector ?? String(label);
                      }}
                    />
                    <Bar dataKey="complaint_count" fill={COLORS.teal} radius={[0, 4, 4, 0]}>
                      <LabelList
                        dataKey="complaint_count"
                        position="right"
                        formatter={(v: unknown) => (v as number).toLocaleString()}
                        style={{ fontSize: 10, fill: '#555', fontWeight: 600 }}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </div>
        </WidgetErrorBoundary>

        {/* Sector summary table */}
        <WidgetErrorBoundary title="Sector Summary">
          <div className="card victim-table-card">
            <span className="widget-title">Sector Impact Summary</span>
            <div className="tab-table-scroll">
              {loading ? <WidgetSkeleton variant="chart" /> : data.industryRisk.length === 0 ? (
                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
              ) : (
                <table className="tab-table">
                  <thead>
                    <tr>
                      <th>Sector</th>
                      <th>Complaints</th>
                      <th>Total Loss</th>
                      <th>Avg Loss / Incident</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...data.industryRisk]
                      .sort((a, b) => b.total_loss - a.total_loss)
                      .map(row => (
                        <tr key={row.sector}>
                          <td>{row.sector}</td>
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

export default VictimProfileTab;
