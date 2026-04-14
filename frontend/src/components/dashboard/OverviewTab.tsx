import React, { useMemo } from 'react';
import './OverviewTab.css';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList,
} from 'recharts';
import StatCard from '../shared/StatCard';
import ComplianceStatusBars from '../shared/ComplianceStatusBars';
import CyberSecurityMap from '../charts/CyberSecurityMap';
import MalwareBarChart from '../charts/MalwareBarChart';
import ProgressGauges from '../shared/ProgressGauges';
import IncidentManagementChart from '../charts/IncidentManagementChart';
import CyberRisksTiles from '../charts/CyberRisksTiles';
import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import SectorAttackHeatmap from '../charts/SectorAttackHeatmap';
import DataFreshness from '../shared/DataFreshness';
import ExecutiveSummaryCard from './ExecutiveSummaryCard';
import VendorAlertsCard from '../shared/VendorAlertsCard';
import type { DashboardData } from '../../hooks/useDashboardData';
import { fmtLoss } from '../../utils/fmtLoss';

function fmtMoney(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${Math.round(v / 1_000)}k`;
  return `$${v}`;
}

function truncate(str: string, max = 22): string {
  return str.length > max ? str.slice(0, max) + '…' : str;
}

import type { AttackTypeStats, IndustryRiskProfile } from '../../api/dashboardSummary';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import AssessmentBanner from '../shared/AssessmentBanner';
import { COLORS } from '../../theme';

interface VictimImpactProps {
    attackTypes: AttackTypeStats[];
    industryRisk: IndustryRiskProfile[];
    loading: boolean;
}

const VictimImpactSection: React.FC<VictimImpactProps> = ({ attackTypes, industryRisk, loading }) => {
    const topLossByAttack = useMemo(
        () => [...attackTypes].sort((a, b) => b.total_loss - a.total_loss).slice(0, 10).map(d => ({ ...d, label: truncate(d.attack_type) })),
        [attackTypes],
    );
    const topAvgLossBySector = useMemo(
        () => [...industryRisk].sort((a, b) => b.avg_loss_per_incident - a.avg_loss_per_incident).slice(0, 10).map(d => ({ ...d, label: truncate(d.sector) })),
        [industryRisk],
    );
    const topComplaintsBySector = useMemo(
        () => [...industryRisk].sort((a, b) => b.complaint_count - a.complaint_count).slice(0, 10).map(d => ({ ...d, label: truncate(d.sector) })),
        [industryRisk],
    );

    return (
        <div className="victim-grid">
            <WidgetErrorBoundary title="Loss by Attack Type">
                <div className="card chart-widget victim-chart">
                    <span className="widget-title">Total Financial Loss by Attack Type</span>
                    <div className="chart-body">
                        {loading ? <WidgetSkeleton variant="chart" /> : topLossByAttack.length === 0 ? (
                            <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={topLossByAttack} layout="vertical" margin={{ top: 4, right: 72, left: 4, bottom: 4 }}>
                                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                    <XAxis type="number" tickFormatter={fmtMoney} tick={{ fontSize: 10 }} />
                                    <YAxis type="category" dataKey="label" width={160} tick={{ fontSize: 10 }} />
                                    <Tooltip formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, 'Total Loss']} labelFormatter={(label: unknown) => { const m = topLossByAttack.find(d => d.label === label); return m?.attack_type ?? String(label); }} />
                                    <Bar dataKey="total_loss" fill={COLORS.red} radius={[0, 4, 4, 0]}>
                                        <LabelList dataKey="total_loss" position="right" formatter={(v: unknown) => fmtMoney(v as number)} style={{ fontSize: 10, fill: '#555', fontWeight: 600 }} />
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </WidgetErrorBoundary>

            <WidgetErrorBoundary title="Avg Loss by Sector">
                <div className="card chart-widget victim-chart">
                    <span className="widget-title">Average Loss per Incident by Sector</span>
                    <div className="chart-body">
                        {loading ? <WidgetSkeleton variant="chart" /> : topAvgLossBySector.length === 0 ? (
                            <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={topAvgLossBySector} layout="vertical" margin={{ top: 4, right: 72, left: 4, bottom: 4 }}>
                                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                    <XAxis type="number" tickFormatter={fmtMoney} tick={{ fontSize: 10 }} />
                                    <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 10 }} />
                                    <Tooltip formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, 'Avg Loss']} labelFormatter={(label: unknown) => { const m = topAvgLossBySector.find(d => d.label === label); return m?.sector ?? String(label); }} />
                                    <Bar dataKey="avg_loss_per_incident" fill={COLORS.navy} radius={[0, 4, 4, 0]}>
                                        <LabelList dataKey="avg_loss_per_incident" position="right" formatter={(v: unknown) => fmtMoney(v as number)} style={{ fontSize: 10, fill: '#555', fontWeight: 600 }} />
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </WidgetErrorBoundary>

            <WidgetErrorBoundary title="Complaints by Sector">
                <div className="card chart-widget victim-chart">
                    <span className="widget-title">Complaint Count by Sector</span>
                    <div className="chart-body">
                        {loading ? <WidgetSkeleton variant="chart" /> : topComplaintsBySector.length === 0 ? (
                            <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>
                        ) : (
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={topComplaintsBySector} layout="vertical" margin={{ top: 4, right: 64, left: 4, bottom: 4 }}>
                                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                    <XAxis type="number" tick={{ fontSize: 10 }} />
                                    <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 10 }} />
                                    <Tooltip formatter={(v: unknown) => [(v as number).toLocaleString(), 'Complaints']} labelFormatter={(label: unknown) => { const m = topComplaintsBySector.find(d => d.label === label); return m?.sector ?? String(label); }} />
                                    <Bar dataKey="complaint_count" fill={COLORS.teal} radius={[0, 4, 4, 0]}>
                                        <LabelList dataKey="complaint_count" position="right" formatter={(v: unknown) => (v as number).toLocaleString()} style={{ fontSize: 10, fill: '#555', fontWeight: 600 }} />
                                    </Bar>
                                </BarChart>
                            </ResponsiveContainer>
                        )}
                    </div>
                </div>
            </WidgetErrorBoundary>

            <WidgetErrorBoundary title="Sector Summary">
                <div className="card victim-table-card">
                    <span className="widget-title">Sector Impact Summary</span>
                    <div className="tab-table-scroll">
                        {loading ? <WidgetSkeleton variant="chart" /> : industryRisk.length === 0 ? (
                            <p style={{ color: '#888', fontSize: 13 }}>No data available.</p>
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
                                    {[...industryRisk].sort((a, b) => b.total_loss - a.total_loss).map(row => (
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
    );
};

function yoyChange(curr: number | undefined, prev: number | undefined): string | undefined {
    if (!curr || !prev || prev === 0) return undefined;
    const pct = ((curr - prev) / prev) * 100;
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(0)}%`;
}

interface Props {
    data: DashboardData;
    loading: boolean;
    loadingHeavy: boolean;
    errors: string[];
    lastUpdated: Date | null;
    onRefresh: () => void;
}

const OverviewTab: React.FC<Props> = ({
    data: dashboardData,
    loading: dashboardLoading,
    loadingHeavy: dashboardLoadingHeavy,
    errors: dashboardErrors,
    lastUpdated,
    onRefresh: refresh,
}) => {
    const sortedTrends = useMemo(
        () => [...dashboardData.temporalTrends].sort((a, b) => b.year - a.year),
        [dashboardData.temporalTrends]
    );
    const thisYear = sortedTrends[0];
    const lastYear = sortedTrends[1];

    const complaintChange = useMemo(
        () => yoyChange(thisYear?.complaint_count, lastYear?.complaint_count),
        [thisYear?.complaint_count, lastYear?.complaint_count]
    );
    const lossChange = useMemo(
        () => yoyChange(thisYear?.total_loss, lastYear?.total_loss),
        [thisYear?.total_loss, lastYear?.total_loss]
    );

    const totalNvdCves = useMemo(
        () => dashboardData.severityDistribution.reduce((s, d) => s + d.count, 0),
        [dashboardData.severityDistribution]
    );
    const pctExploited = useMemo(
        () => totalNvdCves > 0 ? ((dashboardData.kevTotal / totalNvdCves) * 100).toFixed(1) : null,
        [totalNvdCves, dashboardData.kevTotal]
    );

    return (
        <>
            {/* Assessment completeness banner — shown when org profile is incomplete */}
            <AssessmentBanner />

            {/* Toolbar */}
            <div className="overview-toolbar">
                <DataFreshness />
                <button className="overview-refresh-btn" onClick={refresh}>
                    ↻ Refresh
                </button>
                {lastUpdated && (
                    <span className="overview-last-updated">
                        Updated {lastUpdated.toLocaleTimeString()}
                    </span>
                )}
            </div>

            {/* Non-fatal partial errors */}
            {dashboardErrors.length > 0 && (
                <div className="overview-partial-errors">
                    ⚠ Some widgets failed to load: {dashboardErrors.join(' · ')}
                </div>
            )}

            {/* Executive Summary */}
            <ExecutiveSummaryCard
                data={dashboardData.executiveSummary}
                loading={dashboardLoading}
                error={dashboardErrors.find(e => e.startsWith('Executive summary:'))}
            />

            {/* Vendor Alerts summary card */}
            <WidgetErrorBoundary title="Vendor Alerts">
                <VendorAlertsCard />
            </WidgetErrorBoundary>

            <div className="dashboard-grid">
                {/* Top Row */}
                <WidgetErrorBoundary title="Cyber Security Map">
                    <div className="card map-widget chart-widget">
                        <span className="widget-title">Cyber Security</span>
                        <div className="chart-body">
                            <CyberSecurityMap
                                data={dashboardData.geographicThreats}
                                loading={dashboardLoadingHeavy}
                            />
                        </div>
                    </div>
                </WidgetErrorBoundary>
                <WidgetErrorBoundary title="Intrusion Attempts">
                    <div className="card malware-widget chart-widget">
                        <span className="widget-title">Intrusion Attempts by Malware Type</span>
                        <div className="chart-body">
                            <MalwareBarChart
                                data={dashboardData.attackTypes}
                                loading={dashboardLoading}
                            />
                        </div>
                    </div>
                </WidgetErrorBoundary>
                <WidgetErrorBoundary title="Total Intrusion Attempts">
                    <StatCard
                        title="Total Intrusion Attempts"
                        value={dashboardLoading ? '—' : (dashboardData.summary?.total_complaints ?? '—')}
                        valueColor="#d32f2f"
                        change={complaintChange}
                        changeNote={thisYear ? `vs ${thisYear.year - 1}` : undefined}
                    />
                </WidgetErrorBoundary>
                <WidgetErrorBoundary title="Total Financial Losses">
                    <StatCard
                        title="Total Financial Losses"
                        value={dashboardLoading ? '—' : fmtLoss(dashboardData.summary?.total_losses)}
                        valueColor="#3f51b5"
                        change={lossChange}
                        changeNote={thisYear ? `vs ${thisYear.year - 1}` : undefined}
                    />
                </WidgetErrorBoundary>

                {/* Middle Row */}
                <WidgetErrorBoundary title="Progression Gauges">
                    <ProgressGauges
                        data={dashboardData.severityDistribution}
                        loading={dashboardLoading}
                    />
                </WidgetErrorBoundary>
                <WidgetErrorBoundary title="Compliance Status">
                    <ComplianceStatusBars />
                </WidgetErrorBoundary>
                <WidgetErrorBoundary title="Avg Loss per Incident">
                    <StatCard
                        title="Avg Loss per Incident"
                        value={dashboardLoading ? '—' : fmtLoss(dashboardData.summary?.avg_loss_per_incident)}
                        valueColor="#00bcd4"
                    />
                </WidgetErrorBoundary>
                <WidgetErrorBoundary title="CVEs Actively Exploited">
                    <StatCard
                        title="CVEs Actively Exploited"
                        value={dashboardLoading ? '—' : (pctExploited !== null ? `${pctExploited}%` : '—')}
                        valueColor="#e65100"
                        changeNote={totalNvdCves > 0 ? `${dashboardData.kevTotal.toLocaleString()} of ${totalNvdCves.toLocaleString()} CVEs` : undefined}
                    />
                </WidgetErrorBoundary>
                <WidgetErrorBoundary title="Projected Annual Loss">
                    <StatCard
                        title="Projected Annual Loss"
                        value={dashboardLoading ? '—' : (dashboardData.lossProjection?.has_data ? dashboardData.lossProjection.projected_annual_loss_formatted : '—')}
                        valueColor="#7b1fa2"
                        changeNote={dashboardData.lossProjection?.has_data ? `${dashboardData.lossProjection.confidence_level} confidence · ${dashboardData.lossProjection.sector}` : undefined}
                    />
                </WidgetErrorBoundary>

                {/* Bottom Row */}
                <WidgetErrorBoundary title="Incident Management">
                    <div className="card incident-widget chart-widget">
                        <span className="widget-title">Incident Management</span>
                        <div className="chart-body">
                            <IncidentManagementChart
                                data={dashboardData.sectorAttackMatrix}
                                loading={dashboardLoadingHeavy}
                            />
                        </div>
                    </div>
                </WidgetErrorBoundary>
                <WidgetErrorBoundary title="Top Cyber Security Risks">
                    <div className="card risks-widget chart-widget">
                        <span className="widget-title">Top Cyber Security Risks</span>
                        <div className="chart-body">
                            <CyberRisksTiles
                                data={dashboardData.attackTypes}
                                loading={dashboardLoading}
                            />
                        </div>
                    </div>
                </WidgetErrorBoundary>

                {/* Row 4 — Sector × Attack Heatmap */}
                <WidgetErrorBoundary title="Sector × Attack Heatmap">
                    <div className="card heatmap-widget chart-widget">
                        <span className="widget-title">Sector × Attack Type Heatmap</span>
                        <div className="chart-body">
                            <SectorAttackHeatmap
                                data={dashboardData.sectorAttackMatrix}
                                loading={dashboardLoadingHeavy}
                            />
                        </div>
                    </div>
                </WidgetErrorBoundary>
            </div>

            {/* ── Victim Impact Analysis (merged from Victim Profile tab) ── */}
            <h3 style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-secondary, #94a3b8)', textTransform: 'uppercase', letterSpacing: '0.05em', margin: '28px 0 12px' }}>
                Victim Impact Analysis
            </h3>
            <p style={{ fontSize: 12, color: 'var(--text-muted, #64748b)', marginBottom: 16 }}>
                Based on IC3 complaint data — no individual victim data is stored.
            </p>
            <VictimImpactSection
                attackTypes={dashboardData.attackTypes}
                industryRisk={dashboardData.industryRisk}
                loading={dashboardLoadingHeavy}
            />
        </>
    );
};

export default OverviewTab;
