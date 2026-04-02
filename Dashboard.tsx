import React, { useState, useMemo, Suspense, lazy } from 'react';
import { useNavigate } from 'react-router-dom';
import './Dashboard.css';
import { useAuth } from './context/AuthContext';
import { useUserContext } from './context/UserContext';
import { useDarkMode } from './hooks/useDarkMode';
import StatCard from './components/StatCard';
import RiskScoreCard from './components/RiskScoreCard';
import TopIndustryThreats from './components/TopIndustryThreats';
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
import {
    aggregateAttackTypesForSector,
    computePersonalRiskScore,
    filterMatrixBySector,
    getGeographicRow,
    normalizeStateCode,
    resolveSectorFromIndustry,
} from './utils/personalizedDashboard';

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

const US_STATE_NAMES: Record<string, string> = {
    AL: 'Alabama', AK: 'Alaska', AZ: 'Arizona', AR: 'Arkansas', CA: 'California', CO: 'Colorado',
    CT: 'Connecticut', DE: 'Delaware', FL: 'Florida', GA: 'Georgia', HI: 'Hawaii', ID: 'Idaho',
    IL: 'Illinois', IN: 'Indiana', IA: 'Iowa', KS: 'Kansas', KY: 'Kentucky', LA: 'Louisiana',
    ME: 'Maine', MD: 'Maryland', MA: 'Massachusetts', MI: 'Michigan', MN: 'Minnesota', MS: 'Mississippi',
    MO: 'Missouri', MT: 'Montana', NE: 'Nebraska', NV: 'Nevada', NH: 'New Hampshire', NJ: 'New Jersey', NM: 'New Mexico',
    NY: 'New York', NC: 'North Carolina', ND: 'North Dakota', OH: 'Ohio', OK: 'Oklahoma', OR: 'Oregon',
    PA: 'Pennsylvania', RI: 'Rhode Island', SC: 'South Carolina', SD: 'South Dakota', TN: 'Tennessee',
    TX: 'Texas', UT: 'Utah', VT: 'Vermont', VA: 'Virginia', WA: 'Washington', WV: 'West Virginia',
    WI: 'Wisconsin', WY: 'Wyoming', DC: 'Washington D.C.',
};

const Dashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState('overview');
    /** When true, widgets use full aggregate data; when false, filter by org profile (sector / state). */
    const [isGlobal, setIsGlobal] = useState(false);
    const [dark, toggleDark] = useDarkMode();
    const { user, logout } = useAuth();
    const { organization, loading: orgProfileLoading } = useUserContext();
    const navigate = useNavigate();
    const { data: dashboardData, loading: dashboardLoading, loadingHeavy: dashboardLoadingHeavy, errors: dashboardErrors, lastUpdated, refresh } = useDashboardData();

    const isPersonalized = !isGlobal;
    const userCompanyName = organization?.name ?? 'Unknown Company';
    const userIndustry = organization?.industry_label ?? 'Unknown Industry';
    const userState = organization?.primary_state ?? '';
    const userStateCode = normalizeStateCode(organization?.primary_state ?? null);
    const userSector = useMemo(
        () => resolveSectorFromIndustry(organization?.industry_label) ?? organization?.ic3_sector ?? null,
        [organization?.industry_label, organization?.ic3_sector],
    );

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
    const pctExploitedNum = pctExploited !== null ? parseFloat(pctExploited) : null;

    const stateGeoRow = useMemo(
        () => getGeographicRow(dashboardData.geographicThreats, userStateCode),
        [dashboardData.geographicThreats, userStateCode],
    );

    const industryThreatsList = useMemo(() => {
        if (!userSector) return [];
        return aggregateAttackTypesForSector(
            dashboardData.sectorAttackMatrix,
            userSector,
        );
    }, [userSector, dashboardData.sectorAttackMatrix]);

    const attackViewData = useMemo(() => {
        if (!isPersonalized || !userIndustry) return dashboardData.attackTypes;
        return industryThreatsList.length > 0 ? industryThreatsList : dashboardData.attackTypes;
    }, [isPersonalized, userIndustry, industryThreatsList, dashboardData.attackTypes]);

    const matrixForIncident = useMemo(() => {
        if (!isPersonalized || !userSector) return dashboardData.sectorAttackMatrix;
        const rows = filterMatrixBySector(dashboardData.sectorAttackMatrix, userSector);
        return rows.length > 0 ? rows : dashboardData.sectorAttackMatrix;
    }, [isPersonalized, userSector, dashboardData.sectorAttackMatrix]);

    const riskScoreResult = useMemo(() => {
        if (!isPersonalized || !organization) return null;
        return computePersonalRiskScore({
            geographicThreats: dashboardData.geographicThreats,
            sectorAttackMatrix: dashboardData.sectorAttackMatrix,
            userStateCode,
            userSector,
            pctExploited: pctExploitedNum,
        });
    }, [
        isPersonalized,
        organization,
        dashboardData.geographicThreats,
        dashboardData.sectorAttackMatrix,
        userStateCode,
        userSector,
        pctExploitedNum,
    ]);

    const statComplaints = useMemo(() => {
        if (!isPersonalized || !userStateCode || !stateGeoRow) {
            return dashboardData.summary?.total_complaints ?? undefined;
        }
        return stateGeoRow.complaint_count;
    }, [isPersonalized, userStateCode, stateGeoRow, dashboardData.summary?.total_complaints]);

    const statLosses = useMemo(() => {
        if (!isPersonalized || !userStateCode || !stateGeoRow) {
            return dashboardData.summary?.total_losses ?? undefined;
        }
        return stateGeoRow.total_loss;
    }, [isPersonalized, userStateCode, stateGeoRow, dashboardData.summary?.total_losses]);

    const statAvgLoss = useMemo(() => {
        if (!isPersonalized || !userStateCode || !stateGeoRow) {
            return dashboardData.summary?.avg_loss_per_incident ?? undefined;
        }
        return stateGeoRow.avg_loss_per_incident;
    }, [
        isPersonalized,
        userStateCode,
        stateGeoRow,
        dashboardData.summary?.avg_loss_per_incident,
    ]);

    const useStateScopedTrends = isPersonalized && Boolean(userStateCode && stateGeoRow);
    const complaintChangeForCard = useStateScopedTrends ? undefined : complaintChange;
    const lossChangeForCard = useStateScopedTrends ? undefined : lossChange;
    const complaintNote = useStateScopedTrends
        ? `IC3 complaints in ${US_STATE_NAMES[userStateCode!] ?? userStateCode}`
        : thisYear
          ? `vs ${thisYear.year - 1}`
          : undefined;
    const lossNote = useStateScopedTrends
        ? `Reported losses in ${US_STATE_NAMES[userStateCode!] ?? userStateCode}`
        : thisYear
          ? `vs ${thisYear.year - 1}`
          : undefined;

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

            {organization && !orgProfileLoading && (
                <div className="org-profile-banner">
                    <div className="org-profile-banner-main">
                        <span className="org-profile-name">{userCompanyName}</span>
                        <span className="org-profile-meta">{userIndustry}</span>
                        <span className="org-profile-meta">
                            {US_STATE_NAMES[userState] ?? userState}
                        </span>
                    </div>
                    <span className="org-profile-hint">
                        {isPersonalized
                            ? 'Metrics below are weighted for your organization where applicable.'
                            : 'Showing nationwide aggregates. Switch to Personalized for your profile.'}
                    </span>
                </div>
            )}

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
                            <div
                                className="data-scope-toggle"
                                role="group"
                                aria-label="Dashboard data scope"
                            >
                                <button
                                    type="button"
                                    className={isPersonalized ? 'active' : ''}
                                    onClick={() => setIsGlobal(false)}
                                >
                                    Personalized
                                </button>
                                <button
                                    type="button"
                                    className={isGlobal ? 'active' : ''}
                                    onClick={() => setIsGlobal(true)}
                                >
                                    Global
                                </button>
                            </div>
                            <div className="overview-toolbar-actions">
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

                        {isPersonalized && organization && (
                            <div className="personalized-insights-row">
                                <WidgetErrorBoundary title="Your Risk Score">
                                    <RiskScoreCard
                                        result={riskScoreResult}
                                        loading={dashboardLoading || dashboardLoadingHeavy}
                                    />
                                </WidgetErrorBoundary>
                                <WidgetErrorBoundary title="Top industry threats">
                                    <TopIndustryThreats
                                        industryLabel={userIndustry}
                                        data={industryThreatsList}
                                        loading={dashboardLoadingHeavy}
                                    />
                                </WidgetErrorBoundary>
                            </div>
                        )}

                        <div className="dashboard-grid">
                            {/* Top Row */}
                            <WidgetErrorBoundary title="Cyber Security Map">
                                <div className="card map-widget chart-widget">
                                    <span className="widget-title">Cyber Security</span>
                                    <div className="chart-body">
                                        <CyberSecurityMap
                                            data={dashboardData.geographicThreats}
                                            loading={dashboardLoadingHeavy}
                                            highlightState={
                                                isPersonalized ? userState : null
                                            }
                                        />
                                    </div>
                                </div>
                            </WidgetErrorBoundary>
                            <WidgetErrorBoundary title="Intrusion Attempts">
                                <div className="card malware-widget chart-widget">
                                    <span className="widget-title">Intrusion Attempts by Malware Type</span>
                                    <div className="chart-body">
                                        <MalwareBarChart
                                            data={attackViewData}
                                            loading={dashboardLoading}
                                        />
                                    </div>
                                </div>
                            </WidgetErrorBoundary>
                            <WidgetErrorBoundary title="Total Intrusion Attempts">
                                <StatCard
                                    title="Total Intrusion Attempts"
                                    value={dashboardLoading ? '—' : (statComplaints ?? '—')}
                                    valueColor="#d32f2f"
                                    change={complaintChangeForCard}
                                    changeNote={complaintNote}
                                />
                            </WidgetErrorBoundary>
                            <WidgetErrorBoundary title="Total Financial Losses">
                                <StatCard
                                    title="Total Financial Losses"
                                    value={dashboardLoading ? '—' : fmtLoss(statLosses)}
                                    valueColor="#3f51b5"
                                    change={lossChangeForCard}
                                    changeNote={lossNote}
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
                                    value={dashboardLoading ? '—' : fmtLoss(statAvgLoss)}
                                    valueColor="#00bcd4"
                                    changeNote={
                                        useStateScopedTrends && userStateCode
                                            ? `Average in ${US_STATE_NAMES[userStateCode] ?? userStateCode}`
                                            : undefined
                                    }
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

                            {/* Bottom Row */}
                            <WidgetErrorBoundary title="Incident Management">
                                <div className="card incident-widget chart-widget">
                                    <span className="widget-title">Incident Management</span>
                                    <div className="chart-body">
                                        <IncidentManagementChart
                                            data={matrixForIncident}
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
                                            data={attackViewData}
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
                                            highlightSector={
                                                isPersonalized ? userSector : null
                                            }
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
