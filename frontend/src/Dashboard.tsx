import React, { Suspense, lazy, useEffect, useCallback, useMemo } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import './Dashboard.css';
import { useAuth } from './context/AuthContext';
import { useDarkMode } from './hooks/useDarkMode';
import { useDashboardData } from './hooks/useDashboardData';
import DashboardHeader from './components/dashboard/DashboardHeader';
import TabBar from './components/dashboard/TabBar';
import SubTabBar from './components/dashboard/SubTabBar';
import OverviewTab from './components/dashboard/OverviewTab';
import WidgetSkeleton from './components/shared/WidgetSkeleton';
import { API_BASE_URL } from './api/fetchWithAuth';
import { TAB_GROUPS, LEGACY_TAB_MAP } from './config/tabGroups';
import { getVisibleGroups } from './utils/roleUtils';

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

const Dashboard: React.FC = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const [dark, toggleDark] = useDarkMode();
    const { user, logout, orgId, orgLoading, role, orgRole } = useAuth();
    const { data, loading, loadingHeavy, errors, lastUpdated, refresh } = useDashboardData();

    const visibleGroups = useMemo(
        () => getVisibleGroups(TAB_GROUPS, { orgId: orgId ?? null, role, orgRole, orgLoading }),
        [orgId, role, orgRole, orgLoading],
    );

    // --- Resolve active group + sub-tab from URL ---
    const rawTab = searchParams.get('tab');
    const rawSub = searchParams.get('sub');

    // Handle legacy flat tab IDs (e.g. ?tab=findings → ?tab=assessment&sub=findings)
    const resolved = useMemo(() => {
        if (rawTab && LEGACY_TAB_MAP[rawTab] && LEGACY_TAB_MAP[rawTab].sub) {
            return LEGACY_TAB_MAP[rawTab];
        }
        return { tab: rawTab ?? 'overview', sub: rawSub ?? undefined };
    }, [rawTab, rawSub]);

    const activeGroup = resolved.tab;
    const activeGroupDef = visibleGroups.find((g) => g.id === activeGroup);

    const activeSubTab = useMemo(() => {
        if (!activeGroupDef?.subTabs) return activeGroup;
        if (resolved.sub && activeGroupDef.subTabs.some((s) => s.id === resolved.sub)) {
            return resolved.sub;
        }
        return activeGroupDef.subTabs[0].id;
    }, [activeGroupDef, activeGroup, resolved.sub]);

    // If active group isn't visible or is locked, fall back to overview
    useEffect(() => {
        if ((!activeGroupDef || activeGroupDef.locked) && visibleGroups.length > 0) {
            setSearchParams({}, { replace: true });
        }
    }, [activeGroupDef, visibleGroups, setSearchParams]);

    const handleGroupChange = useCallback(
        (groupId: string) => {
            const group = visibleGroups.find((g) => g.id === groupId);
            if (group?.locked) return;
            const params: Record<string, string> = { tab: groupId };
            if (group?.subTabs) {
                params.sub = group.subTabs[0].id;
            }
            setSearchParams(params);
        },
        [visibleGroups, setSearchParams],
    );

    const handleSubTabChange = useCallback(
        (subId: string, groupId?: string) => {
            setSearchParams({ tab: groupId ?? activeGroup, sub: subId });
        },
        [activeGroup, setSearchParams],
    );

    const navigateToFindings = useCallback(() => {
        setSearchParams({ tab: 'assessment', sub: 'findings' });
    }, [setSearchParams]);

    // The component key to render — for standalone groups it's the group id,
    // for groups with sub-tabs it's the active sub-tab id.
    // Locked groups fall back to 'overview' to prevent a flash of gated content.
    const activeComponent = activeGroupDef?.locked
        ? 'overview'
        : (activeGroupDef?.subTabs ? activeSubTab : activeGroup);

    return (
        <div className="dashboard-container">
            <DashboardHeader
                dark={dark}
                onToggleDark={toggleDark}
                user={user}
                onLogout={logout}
            />
            <TabBar
                activeGroup={activeGroup}
                activeSubTab={activeSubTab}
                onGroupChange={handleGroupChange}
                onSubTabChange={handleSubTabChange}
                groups={visibleGroups}
            />

            {activeGroupDef?.subTabs && activeGroupDef.subTabs.length > 1 && (
                <SubTabBar
                    subTabs={activeGroupDef.subTabs}
                    activeSubTab={activeSubTab}
                    onSubTabChange={handleSubTabChange}
                />
            )}

            <main className="dashboard-content">
                {!orgLoading && orgId == null && (
                    <div className="org-join-cta">
                        <span>You are not part of an organization. </span>
                        <Link to="/settings">Join or create an org</Link>
                        <span> to unlock org-specific features.</span>
                    </div>
                )}

                {activeComponent === 'overview' && (
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
                    {activeComponent === 'smbAdvisor' && <SmBAdvisorTab />}
                    {activeComponent === 'findings' && <FindingsTab />}
                    {activeComponent === 'aiSummary' && <AISummaryTab />}
                    {activeComponent === 'dataSources' && <DataSourcesTab onNavigateToFindings={navigateToFindings} />}
                    {activeComponent === 'riskScoring' && <RiskScoringTable apiBaseUrl={API_BASE_URL} />}
                    {activeComponent === 'threatIntel' && <ThreatIntelTab />}
                    {activeComponent === 'trends' && <TrendsTab />}
                    {activeComponent === 'vendorAlerts' && <VendorAlertsTab />}
                    {activeComponent === 'pipelineHealth' && <PipelineHealthTab />}
                    {activeComponent === 'anomalies' && <AnomaliesTab />}
                </Suspense>
            </main>
        </div>
    );
};

export default Dashboard;
