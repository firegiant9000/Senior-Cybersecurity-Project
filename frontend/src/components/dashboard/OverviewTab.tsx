import React, { useMemo, useEffect, useState, useRef, useCallback } from 'react';
import './OverviewTab.css';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LabelList,
  PieChart, Pie, Cell, RadialBarChart, RadialBar,
} from 'recharts';
import StatCard from '../shared/StatCard';
import CyberSecurityMap from '../charts/CyberSecurityMap';
import MalwareBarChart from '../charts/MalwareBarChart';
import ProgressGauges from '../shared/ProgressGauges';
import IncidentManagementChart from '../charts/IncidentManagementChart';
import CyberRisksTiles from '../charts/CyberRisksTiles';
import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import SectorAttackHeatmap from '../charts/SectorAttackHeatmap';
import DataFreshness from '../shared/DataFreshness';
import { formatDateWithTz, formatTimeWithTz } from '../../utils/formatTime';
import ExecutiveSummaryCard from './ExecutiveSummaryCard';
import VendorAlertsCard from '../shared/VendorAlertsCard';
import type { DashboardData } from '../../hooks/useDashboardData';
import { fmtLoss } from '../../utils/fmtLoss';
import { useWidgetPrefs } from '../../hooks/useWidgetPrefs';
import { useRefreshProgress } from '../../hooks/useRefreshProgress';
import RefreshButton from '../RefreshButton';

import { fetchIngestFreshness } from '../../api/ingest';
import { useAuth } from '../../context/AuthContext';
import { canSeePipeline as checkCanSeePipeline } from '../../utils/roleUtils';
import WidgetSkeleton from '../shared/WidgetSkeleton';
import AssessmentBanner from '../shared/AssessmentBanner';
import { COLORS } from '../../theme';
import InfoTip, { getAcronymDefinition } from '../shared/InfoTip';

function fmtMoney(v: number): string {
  if (v >= 1_000_000_000) return `$${(v / 1_000_000_000).toFixed(1)}B`;
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `$${Math.round(v / 1_000)}k`;
  return `$${v}`;
}

function truncate(str: string, max = 22): string {
  return str.length > max ? str.slice(0, max) + '…' : str;
}

const VICTIM_BADGE = (
    <span className="victim-impact-badge">
      IC3<InfoTip text={getAcronymDefinition('IC3')!} label="IC3" /> Victim Financial Impact
    </span>
);

const OVERVIEW_WIDGETS = [
    { id: 'executiveSummary',    label: 'Executive Summary',             moveable: false },
    { id: 'vendorAlerts',        label: 'Vendor Alerts',                 moveable: false },
    { id: 'cyberMap',            label: 'Complaints Map',                moveable: true  },
    { id: 'malwareChart',        label: 'Intrusion Attempts Chart',      moveable: true  },
    { id: 'totalAttempts',       label: 'Total Intrusion Attempts',      moveable: true  },
    { id: 'totalLosses',         label: 'Total Financial Losses',        moveable: true  },
    { id: 'progression',         label: 'Security Posture Gauges',       moveable: true  },
    { id: 'avgLoss',             label: 'Avg Loss per Incident',         moveable: true  },
    { id: 'cvesExploited',       label: 'CVEs Actively Exploited',       moveable: true  },
    { id: 'projectedLoss',       label: 'Projected Annual Loss',         moveable: true  },
    { id: 'attackTypeCount',     label: 'Tracked Attack Vectors',        moveable: true  },
    { id: 'stateCount',          label: 'States with Incidents',         moveable: true  },
    { id: 'totalCves',           label: 'Total CVEs Tracked',            moveable: true  },
    { id: 'avgRiskScore',        label: 'Avg CVE Risk Score',            moveable: true  },
    { id: 'criticalRiskCves',    label: 'CVE Risk Distribution',          moveable: true  },
    { id: 'ic3Anomalies',        label: 'State Threat Anomalies',        moveable: true  },
    { id: 'escalatingSectors',   label: 'Escalating Sectors',            moveable: true  },
    { id: 'incidentMgmt',        label: 'Incident Management',           moveable: true  },
    { id: 'cyberRisks',          label: 'Top Risks · National',          moveable: true  },
    { id: 'heatmap',             label: 'Complaint Volume Heatmap',      moveable: true  },
    { id: 'lossAttack',          label: 'Loss by Attack Type',           moveable: true  },
    { id: 'avgLossSector',       label: 'Avg Loss by Sector',            moveable: true  },
    { id: 'complaintsSector',    label: 'Complaints by Sector',          moveable: true  },
    { id: 'sectorTable',         label: 'Sector Impact Summary',         moveable: true  },
];

const ALL_WIDGET_IDS = OVERVIEW_WIDGETS.map((w) => w.id);

const MOVEABLE_IDS = [
    'cyberMap', 'malwareChart', 'totalAttempts', 'totalLosses',
    'progression', 'avgLoss', 'cvesExploited', 'projectedLoss',
    'attackTypeCount', 'stateCount', 'totalCves',
    'avgRiskScore', 'criticalRiskCves', 'ic3Anomalies', 'escalatingSectors',
    'incidentMgmt', 'cyberRisks', 'heatmap',
    'lossAttack', 'avgLossSector', 'complaintsSector', 'sectorTable',
];

const GRID_SPANS: Record<string, number> = {
    cyberMap: 1, malwareChart: 1, totalAttempts: 1, totalLosses: 1,
    progression: 1, avgLoss: 1, cvesExploited: 1, projectedLoss: 1,
    attackTypeCount: 1, stateCount: 1, totalCves: 1,
    avgRiskScore: 1, criticalRiskCves: 2, ic3Anomalies: 1, escalatingSectors: 1,
    incidentMgmt: 2, cyberRisks: 2, heatmap: 4,
    lossAttack: 2, avgLossSector: 2, complaintsSector: 2, sectorTable: 2,
};

interface GapSlot {
    key: string;
    insertBeforeId: string | null;
    span: number;
}

function computeClickSlots(
    gridOrder: string[],
    hiddenSet: Set<string>,
    selectedId: string,
    spans: Record<string, number>,
): GapSlot[] {
    // Physical gap slots only make sense during drag (where the dragged card creates
    // a visible hole that draws overflow slots toward it). In click-select mode, those
    // same slots appear wherever CSS grid happens to overflow — often several rows away
    // from the selected card, which is confusing and misleading.
    //
    // The swap-target overlay handles ALL card-to-card moves, so physical slots are not
    // needed for reordering. We only show one always-at-the-bottom "Move to end" slot.
    const dragSpan = spans[selectedId] ?? 1;
    const selIdx = gridOrder.indexOf(selectedId);
    const visible = gridOrder.filter((id) => !hiddenSet.has(id) && id !== selectedId);

    // Anchor to the first card that comes after the last visible card in gridOrder
    // (may be hidden). reorder(selected, anchor) places selected just before it, making
    // it appear as the last visible card — without pushing it past hidden cards.
    const lastVisible = visible[visible.length - 1];
    const lastVisibleRawIdx = lastVisible !== undefined ? gridOrder.indexOf(lastVisible) : -1;
    const anchorAfterLast = lastVisibleRawIdx >= 0 ? (gridOrder[lastVisibleRawIdx + 1] ?? null) : null;

    // Skip if the anchor is directly after selected (no-op move)
    if (anchorAfterLast !== null && gridOrder.indexOf(anchorAfterLast) === selIdx + 1) return [];

    return [{ key: 'click-end', insertBeforeId: anchorAfterLast, span: dragSpan }];
}

function computeGapSlots(
    gridOrder: string[],
    hiddenSet: Set<string>,
    dragId: string,
    spans: Record<string, number>,
): GapSlot[] {
    const COLS = 4;
    const dragSpan = spans[dragId] ?? 1;
    const slots: GapSlot[] = [];
    let col = 0;

    // Exclude dragId — simulating without the drag source reveals overflow positions
    // where the widget can be naturally inserted (works for any span width).
    const visible = gridOrder.filter((id) => !hiddenSet.has(id) && id !== dragId);

    for (let i = 0; i < visible.length; i++) {
        const id = visible[i];
        const span = spans[id] ?? 1;
        if (col + span > COLS) {
            const gapWidth = COLS - col;
            const n = Math.floor(gapWidth / dragSpan);
            for (let s = 0; s < n; s++) {
                slots.push({ key: `gap-${i}-${s}`, insertBeforeId: id, span: dragSpan });
            }
            col = 0;
        }
        col += span;
        if (col >= COLS) col = 0;
    }

    if (col > 0) {
        const n = Math.floor((COLS - col) / dragSpan);
        for (let s = 0; s < n; s++) {
            slots.push({ key: `gap-end-${s}`, insertBeforeId: null, span: dragSpan });
        }
    }

    return slots;
}

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
    onSetRefreshProgress?: (callback: (itemName: string) => void) => void;
}

function renderGridWidget(
    id: string,
    dashboardData: DashboardData,
    dashboardLoading: boolean,
    dashboardLoadingHeavy: boolean,
    complaintChange: string | undefined,
    lossChange: string | undefined,
    thisYear: { year: number } | undefined,
    totalNvdCves: number,
    pctExploited: string | null,
) {
    switch (id) {
        case 'cyberMap':
            return (
                <WidgetErrorBoundary key={id} title="Cyber Security Map">
                    <div className="card map-widget chart-widget">
                        <span className="widget-title">Cyber Security Complaints Map</span>
                        <div className="chart-body">
                            <CyberSecurityMap data={dashboardData.geographicThreats} loading={dashboardLoadingHeavy} />
                        </div>
                    </div>
                </WidgetErrorBoundary>
            );
        case 'malwareChart':
            return (
                <WidgetErrorBoundary key={id} title="Intrusion Attempts">
                    <div className="card malware-widget chart-widget">
                        <span className="widget-title">Intrusion Attempts by Malware Type</span>
                        <div className="chart-body">
                            <MalwareBarChart data={dashboardData.attackTypes} loading={dashboardLoading} />
                        </div>
                    </div>
                </WidgetErrorBoundary>
            );
        case 'totalAttempts':
            return (
                <WidgetErrorBoundary key={id} title="Total Intrusion Attempts">
                    <StatCard
                        title="Total Intrusion Attempts"
                        value={dashboardLoading ? '—' : (dashboardData.summary?.total_complaints ?? '—')}
                        valueColor="#d32f2f"
                        change={complaintChange}
                        changeNote={thisYear ? `vs ${thisYear.year - 1}` : undefined}
                    />
                </WidgetErrorBoundary>
            );
        case 'totalLosses':
            return (
                <WidgetErrorBoundary key={id} title="Total Financial Losses">
                    <StatCard
                        title="Total Financial Losses"
                        value={dashboardLoading ? '—' : fmtLoss(dashboardData.summary?.total_losses)}
                        valueColor="#3f51b5"
                        change={lossChange}
                        changeNote={thisYear ? `vs ${thisYear.year - 1}` : undefined}
                    />
                </WidgetErrorBoundary>
            );
        case 'progression':
            return (
                <WidgetErrorBoundary key={id} title="Security Posture">
                    <ProgressGauges data={dashboardData.severityDistribution} kevTotal={dashboardData.kevTotal} loading={dashboardLoading} />
                </WidgetErrorBoundary>
            );
        case 'avgLoss':
            return (
                <WidgetErrorBoundary key={id} title="Avg Loss per Incident">
                    <StatCard
                        title="Avg Loss per Incident"
                        value={dashboardLoading ? '—' : fmtLoss(dashboardData.summary?.avg_loss_per_incident)}
                        valueColor="#00bcd4"
                    />
                </WidgetErrorBoundary>
            );
        case 'cvesExploited':
            return (
                <WidgetErrorBoundary key={id} title="CVEs Actively Exploited">
                    <StatCard
                        title="CVEs Actively Exploited"
                        value={dashboardLoading ? '—' : (pctExploited !== null ? `${pctExploited}%` : '—')}
                        valueColor="#e65100"
                        changeNote={totalNvdCves > 0 ? `${dashboardData.kevTotal.toLocaleString()} of ${totalNvdCves.toLocaleString()} CVEs` : undefined}
                    />
                </WidgetErrorBoundary>
            );
        case 'projectedLoss':
            return (
                <WidgetErrorBoundary key={id} title="Projected Annual Loss">
                    <StatCard
                        title="Projected Annual Loss"
                        value={dashboardLoading ? '—' : (dashboardData.lossProjection?.has_data ? dashboardData.lossProjection.projected_annual_loss_formatted : '—')}
                        valueColor="#7b1fa2"
                        changeNote={dashboardData.lossProjection?.has_data ? `${dashboardData.lossProjection.confidence_level} confidence · ${dashboardData.lossProjection.sector}` : undefined}
                    />
                </WidgetErrorBoundary>
            );

        // ── New info cards ────────────────────────────────────────────────────
        case 'attackTypeCount': {
            const top5Attacks = [...dashboardData.attackTypes]
                .sort((a, b) => b.complaint_count - a.complaint_count)
                .slice(0, 5);
            return (
                <WidgetErrorBoundary key={id} title="Tracked Attack Vectors">
                    <div className="card stat-chart-card">
                        <span className="widget-title">Top Attack Vectors</span>
                        {dashboardLoading ? <WidgetSkeleton variant="chart" /> : (
                            <>
                                <div className="stat-chart-header">
                                    <span className="stat-chart-value" style={{ color: '#00bcd4' }}>
                                        {dashboardData.summary?.attack_type_count ?? '—'}
                                    </span>
                                    <span className="stat-chart-note">unique types tracked</span>
                                </div>
                                <ol className="attack-vector-list">
                                    {top5Attacks.map((a, i) => (
                                        <li key={a.attack_type} className="attack-vector-item">
                                            <span className="attack-vector-rank">#{i + 1}</span>
                                            <span className="attack-vector-name">{a.attack_type}</span>
                                            <span className="attack-vector-count">{a.complaint_count.toLocaleString()}</span>
                                        </li>
                                    ))}
                                </ol>
                            </>
                        )}
                    </div>
                </WidgetErrorBoundary>
            );
        }
        case 'stateCount': {
            const sortedThreats = [...dashboardData.geographicThreats].sort((a, b) => b.complaint_count - a.complaint_count);
            const top3States = sortedThreats.slice(0, 3);
            const otherStateCount = sortedThreats.slice(3).reduce((s, d) => s + d.complaint_count, 0);
            const stateDonutData = [
                ...top3States.map((s) => ({ name: s.state, value: s.complaint_count })),
                ...(otherStateCount > 0 ? [{ name: 'Other', value: otherStateCount }] : []),
            ];
            const STATE_COLORS = ['#00bcd4', '#3f51b5', '#7c4dff', 'rgba(255,255,255,0.12)'];
            return (
                <WidgetErrorBoundary key={id} title="States with Incidents">
                    <div className="card stat-chart-card">
                        <span className="widget-title">States with Incidents</span>
                        <div className="stat-chart-donut-layout">
                            <div className="stat-chart-donut-wrapper">
                                {dashboardLoadingHeavy ? <WidgetSkeleton variant="chart" /> : (
                                    <PieChart width={110} height={110} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                                        <Pie
                                            data={stateDonutData.length > 0 ? stateDonutData : [{ name: 'No data', value: 1 }]}
                                            cx={55} cy={55} innerRadius={33} outerRadius={50}
                                            dataKey="value" startAngle={90} endAngle={-270} strokeWidth={0}
                                        >
                                            {stateDonutData.map((_, i) => (
                                                <Cell key={i} fill={STATE_COLORS[i] ?? 'rgba(255,255,255,0.1)'} />
                                            ))}
                                        </Pie>
                                        <Tooltip formatter={(v: unknown, name: unknown) => [(v as number).toLocaleString(), name as string]} />
                                    </PieChart>
                                )}
                                <div className="stat-chart-donut-center">
                                    <span style={{ color: '#00bcd4', fontSize: 15, fontWeight: 700, lineHeight: 1 }}>
                                        {dashboardLoading ? '—' : (dashboardData.summary?.state_count ?? '—')}
                                    </span>
                                </div>
                            </div>
                            <div className="stat-chart-donut-legend">
                                {dashboardLoadingHeavy ? (
                                    <span className="stat-chart-note">Loading…</span>
                                ) : top3States.map((s, i) => (
                                    <span key={s.state} className="stat-chart-legend-item">
                                        <span className="stat-chart-sev-dot" style={{ background: STATE_COLORS[i] }} />
                                        <span>{s.state} · {s.complaint_count >= 1000 ? `${(s.complaint_count / 1000).toFixed(0)}k` : s.complaint_count.toLocaleString()}</span>
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                </WidgetErrorBoundary>
            );
        }
        case 'totalCves': {
            const SEV_ORDER = ['Critical', 'High', 'Medium', 'Low', 'Unknown'] as const;
            const SEV_COLORS: Record<string, string> = {
                Critical: '#d32f2f', High: '#f57c00', Medium: '#fbc02d', Low: '#388e3c', Unknown: '#757575',
            };
            const sevRow: Record<string, number> = {};
            for (const d of dashboardData.severityDistribution) sevRow[d.severity] = d.count;
            const visibleSevs = SEV_ORDER.filter((k) => (sevRow[k] ?? 0) > 0);
            const sevBarData = [sevRow];
            return (
                <WidgetErrorBoundary key={id} title="Total CVEs Tracked">
                    <div className="card stat-chart-card">
                        <span className="widget-title">Total CVEs Tracked</span>
                        <div className="stat-chart-header">
                            <span className="stat-chart-value" style={{ color: '#3f51b5' }}>
                                {dashboardLoading ? '—' : (totalNvdCves > 0 ? totalNvdCves.toLocaleString() : '—')}
                            </span>
                            <span className="stat-chart-note">
                              in NVD<InfoTip text={getAcronymDefinition('NVD')!} label="NVD" /> database
                            </span>
                        </div>
                        {!dashboardLoading && visibleSevs.length > 0 && (
                            <>
                                <div className="stat-chart-accent-bar">
                                    <ResponsiveContainer width="100%" height={16}>
                                        <BarChart data={sevBarData} layout="vertical" margin={{ top: 0, right: 0, left: 0, bottom: 0 }}>
                                            <XAxis type="number" hide />
                                            <YAxis type="category" hide />
                                            <Tooltip formatter={(v: unknown, name: unknown) => [(v as number).toLocaleString(), name as string]} />
                                            {visibleSevs.map((sev) => (
                                                <Bar key={sev} dataKey={sev} stackId="sev" fill={SEV_COLORS[sev]} />
                                            ))}
                                        </BarChart>
                                    </ResponsiveContainer>
                                </div>
                                <div className="stat-chart-severity-legend">
                                    {visibleSevs.filter((s) => s !== 'Unknown').map((sev) => (
                                        <span key={sev} className="stat-chart-sev-item">
                                            <span className="stat-chart-sev-dot" style={{ background: SEV_COLORS[sev] }} />
                                            {sev}: {(sevRow[sev] ?? 0).toLocaleString()}
                                        </span>
                                    ))}
                                </div>
                            </>
                        )}
                    </div>
                </WidgetErrorBoundary>
            );
        }
        case 'avgRiskScore': {
            const avg = dashboardData.riskScoreStats?.avg_risk ?? 0;
            const gaugeFillEnd = Math.round(180 - (avg / 100) * 180);
            const GAUGE_BG = [{ value: 1, fill: 'rgba(255,255,255,0.15)' }];
            const GAUGE_FG = [{ value: 1, fill: '#7c4dff' }];
            return (
                <WidgetErrorBoundary key={id} title="Avg CVE Risk Score">
                    <div className="card progress-widget gauges-card">
                        <span className="gauges-title">AVG CVE RISK SCORE</span>
                        {dashboardLoading ? <WidgetSkeleton variant="chart" /> : (
                            <>
                                <div className="gauge-item">
                                    <div className="gauge-chart-wrapper">
                                        <ResponsiveContainer width="100%" height={90}>
                                            <RadialBarChart innerRadius="60%" outerRadius="90%" startAngle={180} endAngle={0} data={GAUGE_BG} barSize={12}>
                                                <RadialBar dataKey="value" cornerRadius={6} />
                                            </RadialBarChart>
                                        </ResponsiveContainer>
                                        <ResponsiveContainer width="100%" height={90} style={{ position: 'absolute', top: 0, left: 0 }}>
                                            <RadialBarChart innerRadius="60%" outerRadius="90%" startAngle={180} endAngle={gaugeFillEnd} data={GAUGE_FG} barSize={12}>
                                                <RadialBar dataKey="value" cornerRadius={6} />
                                            </RadialBarChart>
                                        </ResponsiveContainer>
                                    </div>
                                    <span className="gauge-value" style={{ color: '#7c4dff', fontSize: 22 }}>{avg.toFixed(0)}%</span>
                                    <span className="gauge-label">exploitation risk</span>
                                    {dashboardData.riskScoreStats && (
                                        <span className="gauge-sublabel">{dashboardData.riskScoreStats.total.toLocaleString()} CVEs scored</span>
                                    )}
                                </div>
                                <p style={{ fontSize: 10, color: 'rgba(255,255,255,0.38)', textAlign: 'center', margin: '6px 8px 0', lineHeight: 1.4 }}>
                                    Composite score derived from CVSS severity and active exploitation status (KEV). Higher % = greater risk.
                                </p>
                            </>
                        )}
                    </div>
                </WidgetErrorBoundary>
            );
        }
        case 'criticalRiskCves': {
            const riskStats = dashboardData.riskScoreStats;
            const criticalCount = riskStats?.bands.reduce((s, b) => b.min >= 80 ? s + b.count : s, 0) ?? 0;
            const riskTotal = riskStats?.total ?? 0;
            const nonCritCount = Math.max(0, riskTotal - criticalCount);
            const critPct = riskTotal > 0 ? ((criticalCount / riskTotal) * 100).toFixed(1) : null;
            const critDonutData = [
                { name: 'Critical Risk', value: criticalCount },
                { name: 'Other CVEs', value: nonCritCount },
            ];
            const BAND_COLORS: Record<string, string> = {
                Critical: '#d32f2f', High: '#f57c00', Medium: '#fbc02d', Low: '#388e3c',
            };
            const sortedBands = (riskStats?.bands ?? [])
                .slice()
                .sort((a, b) => b.min - a.min)
                .map((b) => ({
                    ...b,
                    shortLabel: b.label.split(' ')[0],
                    color: BAND_COLORS[b.label.split(' ')[0]] ?? '#757575',
                    pct: riskTotal > 0 ? ((b.count / riskTotal) * 100).toFixed(1) : '0.0',
                }));
            const maxBandCount = Math.max(...sortedBands.map((b) => b.count), 1);
            return (
                <WidgetErrorBoundary key={id} title="CVE Risk Distribution">
                    <div className="card stat-chart-card">
                        <span className="widget-title">CVE Risk Distribution</span>
                        {dashboardLoading ? <WidgetSkeleton variant="chart" /> : (
                            <div style={{ display: 'flex', gap: 16, alignItems: 'center', flex: 1 }}>
                                <div className="stat-chart-donut-wrapper" style={{ flex: '0 0 160px', width: 160, height: 160 }}>
                                    <PieChart width={160} height={160} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                                        <Pie
                                            data={riskTotal > 0 ? critDonutData : [{ name: 'No data', value: 1 }]}
                                            cx={80} cy={80} innerRadius={48} outerRadius={72}
                                            dataKey="value" startAngle={90} endAngle={-270} strokeWidth={0}
                                        >
                                            <Cell fill="#d32f2f" />
                                            <Cell fill="rgba(255,255,255,0.08)" />
                                        </Pie>
                                        <Tooltip
                                            contentStyle={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--border)', color: 'var(--text-primary)', fontSize: 12, borderRadius: 6 }}
                                            formatter={(v: unknown, name: unknown) => [(v as number).toLocaleString(), name as string]}
                                        />
                                    </PieChart>
                                    <div className="stat-chart-donut-center">
                                        <span style={{ color: '#d32f2f', fontSize: 16, fontWeight: 700, lineHeight: 1 }}>
                                            {criticalCount.toLocaleString()}
                                        </span>
                                    </div>
                                </div>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 2, flex: '0 0 auto', minWidth: 80 }}>
                                    <span className="stat-chart-value" style={{ color: '#d32f2f' }}>{criticalCount.toLocaleString()}</span>
                                    <span className="stat-chart-note">critical risk CVEs</span>
                                    {critPct && <span className="stat-chart-note">{critPct}% of {riskTotal.toLocaleString()}</span>}
                                </div>
                                <div className="risk-band-grid">
                                    {sortedBands.map((band) => (
                                        <div key={band.label} className="risk-band-row">
                                            <span className="stat-chart-sev-dot" style={{ background: band.color }} />
                                            <span className="risk-band-label">{band.shortLabel}</span>
                                            <div className="risk-band-bar-track">
                                                <div className="risk-band-bar-fill" style={{ width: `${(band.count / maxBandCount) * 100}%`, background: band.color }} />
                                            </div>
                                            <span className="risk-band-count">{band.count.toLocaleString()}</span>
                                            <span className="risk-band-pct">{band.pct}%</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                </WidgetErrorBoundary>
            );
        }
        case 'ic3Anomalies':
            return (
                <WidgetErrorBoundary key={id} title="State Threat Anomalies">
                    <div className="card stat-chart-card">
                        <span className="widget-title">State Threat Anomalies</span>
                        <div className="stat-chart-header">
                            <span className="stat-chart-value" style={{ color: '#d32f2f' }}>
                                {dashboardLoadingHeavy ? '—' : (dashboardData.ic3AnomalyCount != null ? dashboardData.ic3AnomalyCount.toLocaleString() : '—')}
                            </span>
                            <span className="stat-chart-note">states flagged</span>
                        </div>
                        <p className="stat-chart-description">
                            States where complaint volume or financial losses are significantly above the national average. Detected using a statistical z-score — a higher count means more geographic threat clusters are forming.
                        </p>
                    </div>
                </WidgetErrorBoundary>
            );
        case 'escalatingSectors':
            return (
                <WidgetErrorBoundary key={id} title="Escalating Sectors">
                    <div className="card stat-chart-card">
                        <span className="widget-title">Escalating Sectors</span>
                        <div className="stat-chart-header">
                            <span className="stat-chart-value" style={{ color: '#e65100' }}>
                                {dashboardLoadingHeavy ? '—' : (dashboardData.escalatingSectorCount != null ? dashboardData.escalatingSectorCount.toLocaleString() : '—')}
                            </span>
                            <span className="stat-chart-note">sectors surging</span>
                        </div>
                        <p className="stat-chart-description">
                            Industry sectors where year-over-year incident volume or financial losses grew by 50% or more. A sector appearing here has seen a rapid surge in cybercrime activity compared to the prior year.
                        </p>
                    </div>
                </WidgetErrorBoundary>
            );

        case 'incidentMgmt':
            return (
                <WidgetErrorBoundary key={id} title="Incident Management">
                    <div className="card incident-widget chart-widget">
                        <span className="widget-title">Incident Management</span>
                        <div className="chart-body">
                            <IncidentManagementChart data={dashboardData.sectorAttackMatrix} loading={dashboardLoadingHeavy} />
                        </div>
                    </div>
                </WidgetErrorBoundary>
            );
        case 'cyberRisks':
            return (
                <WidgetErrorBoundary key={id} title="Top Cyber Security Risks">
                    <div className="card risks-widget chart-widget">
                        <span className="widget-title">Top Cyber Security Risks · National</span>
                        <div className="chart-body">
                            <CyberRisksTiles data={dashboardData.attackTypes} loading={dashboardLoading} />
                        </div>
                    </div>
                </WidgetErrorBoundary>
            );
        case 'heatmap':
            return (
                <WidgetErrorBoundary key={id} title="Sector × Attack Heatmap">
                    <div className="card heatmap-widget chart-widget">
                        <span className="widget-title">IC3 Complaint Volume · Sector vs. Attack Vector</span>
                        <div className="chart-body">
                            <SectorAttackHeatmap data={dashboardData.sectorAttackMatrix} loading={dashboardLoadingHeavy} />
                        </div>
                    </div>
                </WidgetErrorBoundary>
            );

        // ── Victim Impact widgets ────────────────────────────────────────────
        case 'lossAttack': {
            const data = [...dashboardData.attackTypes]
                .sort((a, b) => b.total_loss - a.total_loss)
                .slice(0, 10)
                .map((d) => ({ ...d, label: truncate(d.attack_type) }));
            return (
                <WidgetErrorBoundary key={id} title="Loss by Attack Type">
                    <div className="card chart-widget">
                        <span className="widget-title">Total Financial Loss by Attack Type</span>
                        <div className="chart-body">
                            {dashboardLoadingHeavy ? <WidgetSkeleton variant="chart" /> : data.length === 0 ? (
                                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={data} layout="vertical" margin={{ top: 4, right: 72, left: 4, bottom: 4 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                        <XAxis type="number" tickFormatter={fmtMoney} tick={{ fontSize: 10 }} />
                                        <YAxis type="category" dataKey="label" width={160} tick={{ fontSize: 10 }} />
                                        <Tooltip formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, 'Total Loss']} labelFormatter={(label: unknown) => { const m = data.find((d) => d.label === label); return m?.attack_type ?? String(label); }} />
                                        <Bar dataKey="total_loss" fill={COLORS.red} radius={[0, 4, 4, 0]}>
                                            <LabelList dataKey="total_loss" position="right" formatter={(v: unknown) => fmtMoney(v as number)} style={{ fontSize: 10, fill: '#555', fontWeight: 600 }} />
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            )}
                        </div>
                        {VICTIM_BADGE}
                    </div>
                </WidgetErrorBoundary>
            );
        }
        case 'avgLossSector': {
            const data = [...dashboardData.industryRisk]
                .sort((a, b) => b.avg_loss_per_incident - a.avg_loss_per_incident)
                .slice(0, 10)
                .map((d) => ({ ...d, label: truncate(d.sector) }));
            return (
                <WidgetErrorBoundary key={id} title="Avg Loss by Sector">
                    <div className="card chart-widget">
                        <span className="widget-title">Average Loss per Incident by Sector</span>
                        <div className="chart-body">
                            {dashboardLoadingHeavy ? <WidgetSkeleton variant="chart" /> : data.length === 0 ? (
                                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={data} layout="vertical" margin={{ top: 4, right: 72, left: 4, bottom: 4 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                        <XAxis type="number" tickFormatter={fmtMoney} tick={{ fontSize: 10 }} />
                                        <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 10 }} />
                                        <Tooltip formatter={(v: unknown) => [`$${(v as number).toLocaleString()}`, 'Avg Loss']} labelFormatter={(label: unknown) => { const m = data.find((d) => d.label === label); return m?.sector ?? String(label); }} />
                                        <Bar dataKey="avg_loss_per_incident" fill={COLORS.navy} radius={[0, 4, 4, 0]}>
                                            <LabelList dataKey="avg_loss_per_incident" position="right" formatter={(v: unknown) => fmtMoney(v as number)} style={{ fontSize: 10, fill: '#555', fontWeight: 600 }} />
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            )}
                        </div>
                        {VICTIM_BADGE}
                    </div>
                </WidgetErrorBoundary>
            );
        }
        case 'complaintsSector': {
            const data = [...dashboardData.industryRisk]
                .sort((a, b) => b.complaint_count - a.complaint_count)
                .slice(0, 10)
                .map((d) => ({ ...d, label: truncate(d.sector) }));
            return (
                <WidgetErrorBoundary key={id} title="Complaints by Sector">
                    <div className="card chart-widget">
                        <span className="widget-title">Complaint Count by Sector</span>
                        <div className="chart-body">
                            {dashboardLoadingHeavy ? <WidgetSkeleton variant="chart" /> : data.length === 0 ? (
                                <p style={{ color: 'var(--text-muted, #6b7280)', fontSize: 13 }}>No data available.</p>
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={data} layout="vertical" margin={{ top: 4, right: 64, left: 4, bottom: 4 }}>
                                        <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                                        <XAxis type="number" tick={{ fontSize: 10 }} />
                                        <YAxis type="category" dataKey="label" width={140} tick={{ fontSize: 10 }} />
                                        <Tooltip formatter={(v: unknown) => [(v as number).toLocaleString(), 'Complaints']} labelFormatter={(label: unknown) => { const m = data.find((d) => d.label === label); return m?.sector ?? String(label); }} />
                                        <Bar dataKey="complaint_count" fill={COLORS.teal} radius={[0, 4, 4, 0]}>
                                            <LabelList dataKey="complaint_count" position="right" formatter={(v: unknown) => (v as number).toLocaleString()} style={{ fontSize: 10, fill: '#555', fontWeight: 600 }} />
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            )}
                        </div>
                        {VICTIM_BADGE}
                    </div>
                </WidgetErrorBoundary>
            );
        }
        case 'sectorTable':
            return (
                <WidgetErrorBoundary key={id} title="Sector Summary">
                    <div className="card victim-table-card">
                        <span className="widget-title">Sector Impact Summary</span>
                        <div className="tab-table-scroll">
                            {dashboardLoadingHeavy ? <WidgetSkeleton variant="chart" /> : dashboardData.industryRisk.length === 0 ? (
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
                                        {[...dashboardData.industryRisk].sort((a, b) => b.total_loss - a.total_loss).map(row => (
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
                        {VICTIM_BADGE}
                    </div>
                </WidgetErrorBoundary>
            );

        default:
            return null;
    }
}

const OverviewTab: React.FC<Props> = ({
    data: dashboardData,
    loading: dashboardLoading,
    loadingHeavy: dashboardLoadingHeavy,
    errors: dashboardErrors,
    lastUpdated,
    onRefresh: refresh,
    onSetRefreshProgress,
}) => {
    const { role, orgRole } = useAuth();
    const pipelineVisible = checkCanSeePipeline(role, orgRole);
    const [lastIngestAt, setLastIngestAt] = useState<string | null>(null);
    const [freshnessRevision, setFreshnessRevision] = useState(0);
    const [showCustomize, setShowCustomize] = useState(false);
    const wasAnyLoadingRef = useRef(dashboardLoading || dashboardLoadingHeavy);
    const gearRef = useRef<HTMLButtonElement>(null);
    const panelRef = useRef<HTMLDivElement>(null);

    // Progress tracking for refresh
    const progressState = useRefreshProgress();

    // Register progress callback with the data hook
    useEffect(() => {
        onSetRefreshProgress?.(progressState.markItemComplete);
    }, [onSetRefreshProgress, progressState.markItemComplete]);

    const { hiddenSet, gridOrder, toggle, move, reorder, insertAtEnd, reset } = useWidgetPrefs(ALL_WIDGET_IDS, MOVEABLE_IDS, 'overviewWidgetPrefs');
    const show = useCallback((id: string) => !hiddenSet.has(id), [hiddenSet]);

    const [dragId, setDragId] = useState<string | null>(null);
    const [overId, setOverId] = useState<string | null>(null);
    const [slotOverKey, setSlotOverKey] = useState<string | null>(null);
    const [selectedId, setSelectedId] = useState<string | null>(null);

    useEffect(() => {
        if (!selectedId) return;
        const handleKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setSelectedId(null); };
        document.addEventListener('keydown', handleKey);
        return () => document.removeEventListener('keydown', handleKey);
    }, [selectedId]);

    useEffect(() => {
        if (!showCustomize) return;
        const handleDown = (e: Event) => {
            const target = e.target as Node | null;
            if (!panelRef.current?.contains(target) && !gearRef.current?.contains(target)) {
                setShowCustomize(false);
            }
        };
        document.addEventListener('mousedown', handleDown);
        return () => document.removeEventListener('mousedown', handleDown);
    }, [showCustomize]);

    const handlePanelKeyDown = useCallback((e: React.KeyboardEvent) => {
        if (e.key === 'Escape') {
            setShowCustomize(false);
            gearRef.current?.focus();
        }
    }, []);

    useEffect(() => {
        if (pipelineVisible) return;
        const controller = new AbortController();
        fetchIngestFreshness(controller.signal)
            .then((r) => {
                const dates = r.sources.map((s) => s.last_run_at).filter(Boolean) as string[];
                if (dates.length > 0) {
                    const latest = dates.reduce((a, b) => (a > b ? a : b));
                    setLastIngestAt(latest);
                }
            })
            .catch(() => { /* non-fatal */ });
        return () => controller.abort();
    }, [pipelineVisible, freshnessRevision]);

    // Reset progress when loading completes
    useEffect(() => {
        const isAnyLoading = dashboardLoading || dashboardLoadingHeavy;
        if (wasAnyLoadingRef.current && !isAnyLoading && progressState.isActive) {
            progressState.reset();
        }
        wasAnyLoadingRef.current = isAnyLoading;
    }, [dashboardLoading, dashboardLoadingHeavy, progressState.reset, progressState.isActive]);

    const handleRefresh = useCallback(() => {
        // Start progress tracking with all items
        progressState.start([
            'Dashboard summary',
            'Attack types',
            'Severity distribution',
            'Temporal trends',
            'KEV total',
            'Executive summary',
            'Loss projection',
            'Risk score stats',
            'Geographic heatmap',
            'Sector attack matrix',
            'Industry risk',
            'IC3 anomalies',
            'Escalating sectors',
        ]);
        refresh();
        setFreshnessRevision((r) => r + 1);
    }, [refresh, progressState.start]);

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

    const panelRows = useMemo(() => {
        const nonMoveable = OVERVIEW_WIDGETS.filter((w) => !w.moveable);
        const moveableInOrder = gridOrder
            .map((id) => OVERVIEW_WIDGETS.find((w) => w.id === id))
            .filter(Boolean) as typeof OVERVIEW_WIDGETS;
        return [...nonMoveable, ...moveableInOrder];
    }, [gridOrder]);

    return (
        <>
            <AssessmentBanner />

            {/* Toolbar */}
            <div className="overview-toolbar-wrapper">
                <div className="overview-toolbar">
                    <div className="overview-toolbar-actions">
                        <button
                            ref={gearRef}
                            className="overview-customize-btn"
                            aria-label="Customize dashboard tabs"
                            title="Customize dashboard tabs"
                            onClick={() => setShowCustomize((v) => !v)}
                        >
                            ⚙ <span className="overview-customize-btn-label">Tabs</span>
                        </button>
                        <RefreshButton
                            onClick={handleRefresh}
                            loading={dashboardLoading || dashboardLoadingHeavy}
                            items={progressState.items}
                            progress={progressState.progress}
                            label="Refresh"
                        />
                        {lastUpdated && (
                            <span className="overview-last-updated">
                                Updated {formatTimeWithTz(lastUpdated)}
                            </span>
                        )}
                    </div>
                    <div className="overview-toolbar-status">
                        <DataFreshness />
                        {!pipelineVisible && lastIngestAt && (
                            <span className="overview-last-updated overview-last-updated--ingest">
                                Data as of: {formatDateWithTz(lastIngestAt)}
                            </span>
                        )}
                    </div>
                </div>

                {showCustomize && (
                    <div ref={panelRef} className="overview-customize-panel" onKeyDown={handlePanelKeyDown}>
                        <div className="overview-customize-panel-header">
                            <span className="overview-customize-title">Customize Widgets</span>
                            <button className="overview-customize-reset-btn" onClick={reset}>Reset</button>
                        </div>
                        {panelRows.map(({ id, label, moveable }) => {
                            const isHidden = hiddenSet.has(id);
                            const orderIdx = moveable ? gridOrder.indexOf(id) : -1;
                            const isFirst = orderIdx === 0;
                            const isLast = orderIdx === gridOrder.length - 1;

                            return (
                                <div key={id} className="overview-customize-row">
                                    <input
                                        type="checkbox"
                                        id={`wc-${id}`}
                                        checked={!isHidden}
                                        onChange={() => toggle(id)}
                                    />
                                    <label htmlFor={`wc-${id}`} className="overview-customize-label">
                                        {label}
                                    </label>
                                    {moveable && (
                                        <div className="overview-customize-arrows">
                                            <button
                                                className="overview-customize-arrow-btn"
                                                onClick={() => move(id, 'up')}
                                                disabled={isFirst}
                                                aria-label={`Move ${label} up`}
                                            >▲</button>
                                            <button
                                                className="overview-customize-arrow-btn"
                                                onClick={() => move(id, 'down')}
                                                disabled={isLast}
                                                aria-label={`Move ${label} down`}
                                            >▼</button>
                                        </div>
                                    )}
                                </div>
                            );
                        })}
                    </div>
                )}
            </div>

            {/* Non-fatal partial errors */}
            {dashboardErrors.length > 0 && (
                <div className="overview-partial-errors">
                    ⚠ Some widgets failed to load: {dashboardErrors.join(' · ')}
                </div>
            )}

            {show('executiveSummary') && (
                <ExecutiveSummaryCard
                    data={dashboardData.executiveSummary}
                    loading={dashboardLoading}
                    error={dashboardErrors.find(e => e.startsWith('Executive summary:'))}
                />
            )}

            {show('vendorAlerts') && (
                <div style={{ marginBottom: 16 }}>
                    <WidgetErrorBoundary title="Vendor Alerts">
                        <VendorAlertsCard />
                    </WidgetErrorBoundary>
                </div>
            )}

            <div className="dashboard-grid">
                {(() => {
                    const activeId = dragId ?? selectedId;
                    const gapSlots = activeId
                        ? (dragId
                            ? computeGapSlots(gridOrder, hiddenSet, activeId, GRID_SPANS)
                            : computeClickSlots(gridOrder, hiddenSet, activeId, GRID_SPANS))
                        : [];
                    const slotMap = new Map<string | null, GapSlot[]>();
                    for (const s of gapSlots) {
                        const arr = slotMap.get(s.insertBeforeId) ?? [];
                        arr.push(s);
                        slotMap.set(s.insertBeforeId, arr);
                    }

                    const renderSlot = (s: GapSlot) => {
                        const isOver = slotOverKey === s.key;
                        const onDrop = (e: React.DragEvent) => {
                            e.preventDefault();
                            if (!dragId) return;
                            if (s.insertBeforeId) reorder(dragId, s.insertBeforeId);
                            else insertAtEnd(dragId);
                            setSlotOverKey(null);
                        };
                        const handleSlotClick = () => {
                            if (!selectedId) return;
                            if (s.insertBeforeId !== null) reorder(selectedId, s.insertBeforeId);
                            else insertAtEnd(selectedId);
                            setSelectedId(null);
                        };
                        return (
                            <div
                                key={s.key}
                                className={`widget-drag-wrapper widget-source-slot widget-gap-target${dragId ? '' : ' widget-gap-target--end'}${isOver ? ' widget-source-slot--over' : ''}`}
                                style={{ gridColumn: `span ${s.span}` }}
                                onClick={handleSlotClick}
                                onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = 'move'; if (slotOverKey !== s.key) setSlotOverKey(s.key); }}
                                onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setSlotOverKey(null); }}
                                onDrop={onDrop}
                            >
                                {!dragId && <span className="widget-gap-end-label">Move here →end</span>}
                            </div>
                        );
                    };

                    const items: React.ReactNode[] = [];

                    for (const id of gridOrder) {
                        if (!show(id)) continue;

                        for (const s of slotMap.get(id) ?? []) items.push(renderSlot(s));

                        const isSource   = dragId === id;
                        const isOver     = overId === id;
                        const isSelected = selectedId === id;
                        const isMoveable = MOVEABLE_IDS.includes(id);
                        const isSwapTarget = selectedId !== null && !isSelected && isMoveable;
                        items.push(
                            <div
                                key={id}
                                className={
                                    'widget-drag-wrapper' +
                                    (isSource ? ' widget-source-slot' : '') +
                                    (isSource && isOver ? ' widget-source-slot--over' : '') +
                                    (!isSource && isOver ? ' widget-drag-over' : '') +
                                    (isSelected ? ' widget-selected' : '') +
                                    (isSwapTarget ? ' widget-swap-target' : '')
                                }
                                style={{ gridColumn: `span ${GRID_SPANS[id] ?? 1}` }}
                                draggable
                                onClick={() => {
                                    if (!isMoveable || dragId) return;
                                    if (isSelected) {
                                        setSelectedId(null);
                                    } else if (selectedId) {
                                        reorder(selectedId, id);
                                        setSelectedId(null);
                                    } else {
                                        setSelectedId(id);
                                    }
                                }}
                                onDragStart={(e) => { e.dataTransfer.effectAllowed = 'move'; setDragId(id); setSelectedId(null); }}
                                onDragOver={(e) => {
                                    e.preventDefault();
                                    e.dataTransfer.dropEffect = 'move';
                                    if (overId !== id) setOverId(id);
                                }}
                                onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) setOverId(null); }}
                                onDrop={(e) => {
                                    e.preventDefault();
                                    if (dragId && dragId !== id) reorder(dragId, id);
                                    setOverId(null);
                                }}
                                onDragEnd={() => { setDragId(null); setOverId(null); setSlotOverKey(null); }}
                            >
                                {!isSource && renderGridWidget(
                                    id, dashboardData, dashboardLoading, dashboardLoadingHeavy,
                                    complaintChange, lossChange, thisYear, totalNvdCves, pctExploited,
                                )}
                                {!isSource && <span className="widget-drag-handle" aria-hidden="true">⠿</span>}
                                {isSwapTarget && (
                                    <div
                                        className="widget-swap-overlay"
                                        onClick={(e) => {
                                            e.stopPropagation();
                                            if (selectedId) { reorder(selectedId, id); setSelectedId(null); }
                                        }}
                                    />
                                )}
                            </div>
                        );
                    }

                    for (const s of slotMap.get(null) ?? []) items.push(renderSlot(s));

                    return items;
                })()}
            </div>
        </>
    );
};

export default OverviewTab;
