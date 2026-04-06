import React, { useState, useMemo, Suspense, lazy } from 'react';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css';
import { useAuth } from './context/AuthContext';
import { useDarkMode } from './hooks/useDarkMode';
import StatCard from './components/StatCard';
import ComplianceStatusBars from './components/ComplianceStatusBars';
import CyberSecurityMap from './components/CyberSecurityMap';
import MalwareBarChart from './components/MalwareBarChart';
import ProgressGauges from './components/ProgressGauges';
import IncidentManagementChart from './components/IncidentManagementChart';
import CyberRisksTiles from './components/CyberRisksTiles';
import WidgetErrorBoundary from './components/WidgetErrorBoundary';
import SectorAttackHeatmap from './components/SectorAttackHeatmap';
import WidgetSkeleton from './components/WidgetSkeleton';
import DataFreshness from './components/DataFreshness';
import ExecutiveSummaryCard from './components/ExecutiveSummaryCard';
import { useDashboardData } from './hooks/useDashboardData';

// Tab components are lazy-loaded so they are excluded from the initial bundle
const EconomicsTable = lazy(() => import('./components/EconomicsTable'));
const CisaKevTable = lazy(() => import('./components/CisaKevTable'));
const NvdTable = lazy(() => import('./components/NvdTable'));
const IC3Table = lazy(() => import('./components/IC3Table'));
const RiskScoringTable = lazy(() => import('./components/RiskScoringTable'));
const ThreatIntelTab = lazy(() => import('./components/ThreatIntelTab'));
const TrendsTab = lazy(() => import('./components/TrendsTab'));
const AlertsFeedTab = lazy(() => import('./components/AlertsFeedTab'));
const VictimProfileTab = lazy(() => import('./components/VictimProfileTab'));
const PipelineHealthTab = lazy(() => import('./components/PipelineHealthTab'));
const SmBAdvisorTab = lazy(() => import('./components/SmBAdvisorTab'));
const VendorAlertsTab = lazy(() => import('./components/VendorAlertsTab'));

import VendorAlertsCard from './components/VendorAlertsCard';
import { API_BASE_URL } from './api/fetchWithAuth';
import { fmtLoss } from './utils/fmtLoss';

function yoyChange(curr: number | undefined, prev: number | undefined): string | undefined {
    if (!curr || !prev || prev === 0) return undefined;
    const pct = ((curr - prev) / prev) * 100;
    return `${pct >= 0 ? '+' : ''}${pct.toFixed(0)}%`;
}

const Dashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState('overview');
    const [dark, toggleDark] = useDarkMode();
    const { user, logout } = useAuth();
    const navigate = useNavigate();
    const { data: dashboardData, loading: dashboardLoading, loadingHeavy: dashboardLoadingHeavy, errors: dashboardErrors, lastUpdated, refresh } = useDashboardData();

    // ── Year-over-year change helpers ────────────────────────────────────────
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

    // ── % CVEs actively exploited ────────────────────────────────────────────
    const totalNvdCves = useMemo(
        () => dashboardData.severityDistribution.reduce((s, d) => s + d.count, 0),
        [dashboardData.severityDistribution]
    );
    const pctExploited = useMemo(
        () => totalNvdCves > 0 ? ((dashboardData.kevTotal / totalNvdCves) * 100).toFixed(1) : null,
        [totalNvdCves, dashboardData.kevTotal]
    );

    return (
        <div className="dashboard-container">
            {/* Header */}
            <header className="dashboard-header">
                <h1>Hacker Tracker</h1>
                <div className="header-buttons">
                    <button className="dark-mode-btn" onClick={toggleDark} title="Toggle dark mode">
                        {dark ? '☀' : '🌙'}
                    </button>
                    {user ? (
                        <>
                            <span className="header-user-email">{user.email}</span>
                            <button onClick={() => navigate('/settings')}>Settings</button>
                            <button onClick={async () => { await logout(); navigate('/login'); }}>Log Out</button>
                        </>
                    ) : (
                        <>
                            <button onClick={() => navigate('/login')}>Log In</button>
                            <button onClick={() => navigate('/login')}>Sign Up</button>
                        </>
                    )}
                </div>
            </header>

            {/* Tabs */}
            <div className="tabs-container">
                <button
                    className={`tab ${activeTab === 'smbAdvisor' ? 'active' : ''}`}
                    onClick={() => setActiveTab('smbAdvisor')}
                >
                    SMB Risk Advisor
                </button>
                <button
                    className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
                    onClick={() => setActiveTab('overview')}
                >
                    Overview
                </button>
                <button
                    className={`tab ${activeTab === 'economics' ? 'active' : ''}`}
                    onClick={() => setActiveTab('economics')}
                >
                    Economics
                </button>
                <button
                    className={`tab ${activeTab === 'riskScoring' ? 'active' : ''}`}
                    onClick={() => setActiveTab('riskScoring')}
                >
                    Risk Scoring
                </button>
                <button
                    className={`tab ${activeTab === 'cisa' ? 'active' : ''}`}
                    onClick={() => setActiveTab('cisa')}
                >
                    CISA KEV
                </button>
                <button
                    className={`tab ${activeTab === 'nvd' ? 'active' : ''}`}
                    onClick={() => setActiveTab('nvd')}
                >
                    NVD
                </button>
                <button
                    className={`tab ${activeTab === 'ic3' ? 'active' : ''}`}
                    onClick={() => setActiveTab('ic3')}
                >
                    IC3
                </button>
                <button
                    className={`tab ${activeTab === 'threatIntel' ? 'active' : ''}`}
                    onClick={() => setActiveTab('threatIntel')}
                >
                    Threat Intelligence
                </button>
                <button
                    className={`tab ${activeTab === 'trends' ? 'active' : ''}`}
                    onClick={() => setActiveTab('trends')}
                >
                    Trends
                </button>
                <button
                    className={`tab ${activeTab === 'alerts' ? 'active' : ''}`}
                    onClick={() => setActiveTab('alerts')}
                >
                    Alerts Feed
                </button>
                <button
                    className={`tab ${activeTab === 'vendorAlerts' ? 'active' : ''}`}
                    onClick={() => setActiveTab('vendorAlerts')}
                >
                    Vendor Alerts
                </button>
                <button
                    className={`tab ${activeTab === 'victimProfile' ? 'active' : ''}`}
                    onClick={() => setActiveTab('victimProfile')}
                >
                    Victim Profile
                </button>
                <button
                    className={`tab ${activeTab === 'pipelineHealth' ? 'active' : ''}`}
                    onClick={() => setActiveTab('pipelineHealth')}
                >
                    Pipeline Health
                </button>
            </div>

            {/* Main Content */}
            <main className="dashboard-content">
                {activeTab === 'overview' && (
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

                        {/* Executive Summary — prominent card at top of dashboard */}
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
                                    changeNote={dashboardData.lossProjection ? `${dashboardData.lossProjection.confidence_level} confidence · ${dashboardData.lossProjection.sector}` : undefined}
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
                )}

                <Suspense fallback={<WidgetSkeleton />}>
                    {activeTab === 'smbAdvisor' && <SmBAdvisorTab />}
                    {activeTab === 'economics' && <EconomicsTable apiBaseUrl={API_BASE_URL} />}
                    {activeTab === 'riskScoring' && <RiskScoringTable apiBaseUrl={API_BASE_URL} />}
                    {activeTab === 'cisa' && <CisaKevTable apiBaseUrl={API_BASE_URL} />}
                    {activeTab === 'nvd' && <NvdTable apiBaseUrl={API_BASE_URL} />}
                    {activeTab === 'ic3' && <IC3Table apiBaseUrl={API_BASE_URL} />}
                    {activeTab === 'threatIntel' && <ThreatIntelTab />}
                    {activeTab === 'trends' && <TrendsTab />}
                    {activeTab === 'alerts' && <AlertsFeedTab />}
                    {activeTab === 'vendorAlerts' && <VendorAlertsTab />}
                    {activeTab === 'victimProfile' && <VictimProfileTab />}
                    {activeTab === 'pipelineHealth' && <PipelineHealthTab />}
                </Suspense>
            </main>
        </div>
    );
};

export default Dashboard;
