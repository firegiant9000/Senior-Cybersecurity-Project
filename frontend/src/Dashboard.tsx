import React, { useState, Suspense, lazy, useEffect } from 'react';
import { Link } from 'react-router-dom';
import './Dashboard.css';
import { useAuth } from './context/AuthContext';
import { useDarkMode } from './hooks/useDarkMode';
import { useDashboardData } from './hooks/useDashboardData';
import DashboardHeader from './components/dashboard/DashboardHeader';
import TabBar, { type TabDef } from './components/dashboard/TabBar';
import OverviewTab from './components/dashboard/OverviewTab';
import WidgetSkeleton from './components/shared/WidgetSkeleton';
import { API_BASE_URL } from './api/fetchWithAuth';
import { canSeePipeline as checkCanSeePipeline } from './utils/roleUtils';

const RiskScoringTable = lazy(() => import('./components/tabs/RiskScoringTable'));
const ThreatIntelTab = lazy(() => import('./components/tabs/ThreatIntelTab'));
const TrendsTab = lazy(() => import('./components/tabs/TrendsTab'));
const PipelineHealthTab = lazy(() => import('./components/tabs/PipelineHealthTab'));
const SmBAdvisorTab = lazy(() => import('./components/tabs/SmBAdvisorTab'));
const VendorAlertsTab = lazy(() => import('./components/tabs/VendorAlertsTab'));
const DataSourcesTab = lazy(() => import('./components/tabs/DataSourcesTab'));
const FindingsTab = lazy(() => import('./components/tabs/FindingsTab'));
const AISummaryTab = lazy(() => import('./components/tabs/AISummaryTab'));
const AnomaliesTab = lazy(() => import('./components/tabs/AnomaliesTab'));

const ALL_TABS: TabDef[] = [
    { id: 'smbAdvisor', label: 'SMB Risk Advisor' },
    { id: 'overview', label: 'Overview' },
    { id: 'findings', label: 'Findings' },
    { id: 'aiSummary', label: 'AI Summary' },
    { id: 'dataSources', label: 'Data Sources' },
    { id: 'riskScoring', label: 'Risk Scoring' },
    { id: 'threatIntel', label: 'Threat Intelligence' },
    { id: 'trends', label: 'Trends' },
    { id: 'vendorAlerts', label: 'Vendor Alerts' },
    { id: 'pipelineHealth', label: 'Pipeline Health' },
    { id: 'anomalies', label: 'Anomalies' },
];

const ORG_ONLY_TABS = new Set(['smbAdvisor', 'findings', 'aiSummary', 'vendorAlerts']);

const Dashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState('overview');
    const [dark, toggleDark] = useDarkMode();
    const { user, logout, orgId, orgLoading, role, orgRole } = useAuth();
    const { data, loading, loadingHeavy, errors, lastUpdated, refresh } = useDashboardData();

    const canSeePipeline = checkCanSeePipeline(role, orgRole);

    const tabs = orgLoading
        ? ALL_TABS.filter((t) => !ORG_ONLY_TABS.has(t.id) && t.id !== 'pipelineHealth')
        : ALL_TABS.filter((t) => {
            if (ORG_ONLY_TABS.has(t.id) && orgId == null) return false;
            if (t.id === 'pipelineHealth' && !canSeePipeline) return false;
            return true;
          });

    useEffect(() => {
        if (!tabs.find((t) => t.id === activeTab)) {
            setActiveTab('overview');
        }
    }, [tabs]);

    return (
        <div className="dashboard-container">
            <DashboardHeader
                dark={dark}
                onToggleDark={toggleDark}
                user={user}
                onLogout={logout}
            />
            <TabBar activeTab={activeTab} onTabChange={setActiveTab} tabs={tabs} />

            <main className="dashboard-content">
                {!orgLoading && orgId == null && (
                    <div className="org-join-cta">
                        <span>You are not part of an organization. </span>
                        <Link to="/settings">Join or create an org</Link>
                        <span> to unlock org-specific features.</span>
                    </div>
                )}
                {activeTab === 'overview' && (
                    <OverviewTab
                        data={data}
                        loading={loading}
                        loadingHeavy={loadingHeavy}
                        errors={errors}
                        lastUpdated={lastUpdated}
                        onRefresh={refresh}
                    />
                )}

                <Suspense fallback={<WidgetSkeleton />}>
                    {activeTab === 'smbAdvisor' && <SmBAdvisorTab />}
                    {activeTab === 'findings' && <FindingsTab />}
                    {activeTab === 'aiSummary' && <AISummaryTab />}
                    {activeTab === 'dataSources' && <DataSourcesTab onNavigateToFindings={() => setActiveTab('findings')} />}
                    {activeTab === 'riskScoring' && <RiskScoringTable apiBaseUrl={API_BASE_URL} />}
                    {activeTab === 'threatIntel' && <ThreatIntelTab />}
                    {activeTab === 'trends' && <TrendsTab />}
                    {activeTab === 'vendorAlerts' && <VendorAlertsTab />}
                    {activeTab === 'pipelineHealth' && <PipelineHealthTab />}
                    {activeTab === 'anomalies' && <AnomaliesTab />}
                </Suspense>
            </main>
        </div>
    );
};

export default Dashboard;
