import React, { useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useDashboardData } from '../hooks/useDashboardData';
import OverviewTab from '../components/dashboard/OverviewTab';
import { logActivationEvent } from '../api/analytics';

export default function OverviewPage(): React.JSX.Element {
  const { user, orgId } = useAuth();
  const { data, loading, loadingHeavy, errors, lastUpdated, refresh, setOnProgress } = useDashboardData();

  // Emit `dashboard_first_view` at most once per browser session so the
  // funnel knows when a user actually reaches a populated dashboard.
  useEffect(() => {
    if (user == null) return;
    const KEY = 'ht.dashboardFirstViewSent';
    if (window.sessionStorage.getItem(KEY)) return;
    window.sessionStorage.setItem(KEY, '1');
    void logActivationEvent({
      event_type: 'dashboard_first_view',
      org_id: orgId ?? null,
    });
  }, [user, orgId]);

  return (
    <OverviewTab
      data={data}
      loading={loading}
      loadingHeavy={loadingHeavy}
      errors={errors}
      lastUpdated={lastUpdated}
      onRefresh={refresh}
      onSetRefreshProgress={setOnProgress}
    />
  );
}
