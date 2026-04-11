import React, { useMemo } from 'react';
import './OverviewTab.css';
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
        </>
    );
};

export default OverviewTab;
