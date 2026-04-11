import React, { useState, Suspense, lazy } from 'react';
import './Dashboard.css';
import { useAuth } from './context/AuthContext';
import { useDarkMode } from './hooks/useDarkMode';
import { useDashboardData } from './hooks/useDashboardData';
import DashboardHeader from './components/dashboard/DashboardHeader';
import TabBar, { type TabDef } from './components/dashboard/TabBar';
import OverviewTab from './components/dashboard/OverviewTab';
import WidgetSkeleton from './components/shared/WidgetSkeleton';
import { API_BASE_URL } from './api/fetchWithAuth';

const EconomicsTable = lazy(() => import('./components/tabs/EconomicsTable'));
const CisaKevTable = lazy(() => import('./components/tabs/CisaKevTable'));
const NvdTable = lazy(() => import('./components/tabs/NvdTable'));
const IC3Table = lazy(() => import('./components/tabs/IC3Table'));
const RiskScoringTable = lazy(() => import('./components/tabs/RiskScoringTable'));
const ThreatIntelTab = lazy(() => import('./components/tabs/ThreatIntelTab'));
const TrendsTab = lazy(() => import('./components/tabs/TrendsTab'));
const AlertsFeedTab = lazy(() => import('./components/tabs/AlertsFeedTab'));
const VictimProfileTab = lazy(() => import('./components/tabs/VictimProfileTab'));
const PipelineHealthTab = lazy(() => import('./components/tabs/PipelineHealthTab'));
const SmBAdvisorTab = lazy(() => import('./components/tabs/SmBAdvisorTab'));
const VendorAlertsTab = lazy(() => import('./components/tabs/VendorAlertsTab'));

const TABS: TabDef[] = [
    { id: 'smbAdvisor', label: 'SMB Risk Advisor' },
    { id: 'overview', label: 'Overview' },
    { id: 'economics', label: 'Economics' },
    { id: 'riskScoring', label: 'Risk Scoring' },
    { id: 'cisa', label: 'CISA KEV' },
    { id: 'nvd', label: 'NVD' },
    { id: 'ic3', label: 'IC3' },
    { id: 'threatIntel', label: 'Threat Intelligence' },
    { id: 'trends', label: 'Trends' },
    { id: 'alerts', label: 'Alerts Feed' },
    { id: 'vendorAlerts', label: 'Vendor Alerts' },
    { id: 'victimProfile', label: 'Victim Profile' },
    { id: 'pipelineHealth', label: 'Pipeline Health' },
];

const Dashboard: React.FC = () => {
    const [activeTab, setActiveTab] = useState('overview');
    const [dark, toggleDark] = useDarkMode();
    const { user, logout } = useAuth();
    const { data, loading, loadingHeavy, errors, lastUpdated, refresh } = useDashboardData();

    return (
        <div className="dashboard-container">
            <DashboardHeader
                dark={dark}
                onToggleDark={toggleDark}
                user={user}
                onLogout={logout}
            />
            <TabBar activeTab={activeTab} onTabChange={setActiveTab} tabs={TABS} />

            <main className="dashboard-content">
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
