import React, { useEffect, useState, useRef, useCallback } from 'react';
import './OverviewTab.css';
import WidgetErrorBoundary from '../shared/WidgetErrorBoundary';
import DataFreshness from '../shared/DataFreshness';
import { formatDateWithTz, formatTimeWithTz } from '../../utils/formatTime';
import ProjectedLossCard from './ProjectedLossCard';
import VendorAlertsCard from '../shared/VendorAlertsCard';
import EmergingThreatsCard from './EmergingThreatsCard';
import type { DashboardData } from '../../hooks/useDashboardData';
import { useRefreshProgress } from '../../hooks/useRefreshProgress';
import RefreshButton from '../RefreshButton';

import { fetchIngestFreshness } from '../../api/ingest';
import { useAuth } from '../../context/AuthContext';
import { isPlatformAdmin } from '../../utils/roleUtils';
import AssessmentBanner from '../shared/AssessmentBanner';
import NextStepsCard from './NextStepsCard';
import InventoryHealthCard from './InventoryHealthCard';
import SourceBadge from '../shared/SourceBadge';
import ThreatOverviewWidget from './ThreatOverviewWidget';

interface Props {
    data: DashboardData;
    loading: boolean;
    loadingHeavy: boolean;
    errors: string[];
    lastUpdated: Date | null;
    onRefresh: () => void;
    onSetRefreshProgress?: (callback: (itemName: string) => void) => void;
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
    const { role } = useAuth();
    const pipelineVisible = isPlatformAdmin(role);
    const [lastIngestAt, setLastIngestAt] = useState<string | null>(null);
    const [freshnessRevision, setFreshnessRevision] = useState(0);
    const wasAnyLoadingRef = useRef(dashboardLoading || dashboardLoadingHeavy);

    // Progress tracking for refresh
    const progressState = useRefreshProgress();
    const { markItemComplete, reset: resetProgress, start: startProgress, isActive: progressActive } = progressState;

    // Register progress callback with the data hook
    useEffect(() => {
        onSetRefreshProgress?.(markItemComplete);
    }, [onSetRefreshProgress, markItemComplete]);

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
        if (wasAnyLoadingRef.current && !isAnyLoading && progressActive) {
            resetProgress();
        }
        wasAnyLoadingRef.current = isAnyLoading;
    }, [dashboardLoading, dashboardLoadingHeavy, resetProgress, progressActive]);

    const handleRefresh = useCallback(() => {
        // Start progress tracking with all items
        startProgress([
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
    }, [refresh, startProgress]);

    return (
        <>
            <AssessmentBanner />

            {/* Phase B4: post-signup "what's next" nudge — auto-hides
                once the user reaches ENHANCED or marks intake complete. */}
            <NextStepsCard />

            {/* Toolbar */}
            <div className="overview-toolbar-wrapper">
                <div className="overview-toolbar">
                    <div className="overview-toolbar-actions">
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
            </div>

            {/* Non-fatal partial errors */}
            {dashboardErrors.length > 0 && (
                <div className="overview-partial-errors">
                    ⚠ Some widgets failed to load: {dashboardErrors.join(' · ')}
                </div>
            )}

            {/* Phase F3: Inventory health summary — only renders when the user has an org. */}
            <div className="overview-wide-card-slot">
                <WidgetErrorBoundary title="Inventory Health">
                    <InventoryHealthCard />
                </WidgetErrorBoundary>
            </div>

            <div className="overview-wide-card-slot overview-badged-slot">
                <WidgetErrorBoundary title="Vendor Alerts">
                    <VendorAlertsCard />
                </WidgetErrorBoundary>
                <SourceBadge datasetKey="vendor_alerts" className="widget-source-badge" />
            </div>

            <div className="overview-wide-card-slot overview-badged-slot">
                <WidgetErrorBoundary title="Projected Annual Loss">
                    <ProjectedLossCard data={dashboardData.lossProjection} loading={dashboardLoading} />
                </WidgetErrorBoundary>
                <SourceBadge datasetKey="loss_projection" className="widget-source-badge" />
            </div>

            <WidgetErrorBoundary title="Threat Intelligence Overview">
                <ThreatOverviewWidget data={dashboardData} loading={dashboardLoading} />
            </WidgetErrorBoundary>

            <div className="overview-wide-card-slot overview-badged-slot">
                <WidgetErrorBoundary title="Emerging Threats">
                    <EmergingThreatsCard />
                </WidgetErrorBoundary>
                <SourceBadge datasetKey="kev" className="widget-source-badge" />
            </div>
        </>
    );
};

export default OverviewTab;
