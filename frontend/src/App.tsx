import { lazy } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import LoginPage from "./pages/LoginPage.tsx";
import LandingPage from "./pages/LandingPage.tsx";
import SettingsPage from "./pages/SettingsPage.tsx";
import AssessmentDebugPage from "./pages/AssessmentDebugPage.tsx";
import AssessmentIntakePage from "./pages/AssessmentIntakePage.tsx";
import OrgProfilePage from "./pages/OrgProfilePage.tsx";
import AcceptInvitePage from "./pages/AcceptInvitePage.tsx";
import ExecutiveReportPage from "./pages/ExecutiveReportPage.tsx";
import GlossaryPage from "./pages/GlossaryPage.tsx";
import PrivacyPage from "./pages/PrivacyPage.tsx";
import DataHandlingPage from "./pages/DataHandlingPage.tsx";
import UploadInventoryPage from "./pages/UploadInventoryPage.tsx";
import NotFoundPage from "./pages/NotFoundPage.tsx";
import IntegrationsPage from "./pages/IntegrationsPage.tsx";
import OverviewPage from "./pages/OverviewPage.tsx";
import ProtectedRoute from "./components/ProtectedRoute.tsx";
import LegacyRedirect from "./components/LegacyRedirect.tsx";
import RequirePlatformAdmin from "./components/RequirePlatformAdmin.tsx";
import AppShell from "./components/shell/AppShell.tsx";
import DemoBanner from "./components/DemoBanner.tsx";
import { useAuth } from "./context/AuthContext.tsx";

const TrendsTab = lazy(() => import("./components/tabs/TrendsTab"));
const PipelineHealthTab = lazy(() => import("./components/tabs/PipelineHealthTab"));
const NormalizationLogTab = lazy(() => import("./components/tabs/NormalizationLogTab"));
const SmBAdvisorTab = lazy(() => import("./components/tabs/SmBAdvisorTab"));
const VendorAlertsTab = lazy(() => import("./components/tabs/VendorAlertsTab"));
const DataSourcesTab = lazy(() => import("./components/tabs/DataSourcesTab"));
const FindingsTab = lazy(() => import("./components/tabs/FindingsTab"));
const AISummaryTab = lazy(() => import("./components/tabs/AISummaryTab"));
const AnomaliesTab = lazy(() => import("./components/tabs/AnomaliesTab"));
const AssetsPage = lazy(() => import("./pages/AssetsPage"));
const VulnerabilitiesScreen = lazy(() => import("./components/intel/VulnerabilitiesScreen"));

function RootRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/overview" replace />;
  return <LandingPage />;
}

function App() {
  return (
    <>
      <DemoBanner />
    <Routes>
      <Route path="/" element={<RootRoute />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<LoginPage defaultSignUp={true} />} />
      <Route
        element={
          <ProtectedRoute requireOrg={false}>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/onboarding" element={<AssessmentIntakePage />} />
        <Route path="/invites/:token" element={<AcceptInvitePage />} />
        <Route path="/glossary" element={<GlossaryPage />} />
      </Route>
      {/* Legacy URLs sit outside ProtectedRoute and the shell, so the target route's guard applies. */}
      <Route path="/dashboard" element={<LegacyRedirect />} />
      <Route path="/assets" element={<LegacyRedirect />} />
      <Route path="/inventory/upload" element={<LegacyRedirect />} />
      <Route path="/integrations" element={<LegacyRedirect />} />
      <Route path="/report/executive" element={<LegacyRedirect />} />
      <Route path="/settings" element={<LegacyRedirect />} />
      <Route path="/settings/assessment-debug" element={<LegacyRedirect />} />
      <Route path="/org-profile" element={<LegacyRedirect />} />
      <Route path="/assessment-intake" element={<LegacyRedirect />} />
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/overview" element={<OverviewPage />} />
        <Route path="/org/assets" element={<AssetsPage />} />
        <Route path="/org/assets/upload" element={<UploadInventoryPage />} />
        <Route path="/org/findings" element={<FindingsTab />} />
        <Route path="/org/vendor-alerts" element={<VendorAlertsTab />} />
        <Route path="/org/risk" element={<SmBAdvisorTab />} />
        <Route path="/org/briefing" element={<AISummaryTab />} />
        <Route path="/intel/vulnerabilities" element={<VulnerabilitiesScreen />} />
        <Route path="/intel/anomalies" element={<Navigate to="ic3" replace />} />
        <Route path="/intel/anomalies/:view" element={<AnomaliesTab />} />
        <Route path="/intel/trends" element={<TrendsTab />} />
        <Route path="/intel/reference" element={<Navigate to="ic3" replace />} />
        <Route path="/intel/reference/:dataset" element={<DataSourcesTab />} />
        <Route
          path="/admin/pipeline"
          element={
            <RequirePlatformAdmin>
              <PipelineHealthTab />
            </RequirePlatformAdmin>
          }
        />
        <Route
          path="/admin/normalization-log"
          element={
            <RequirePlatformAdmin>
              <NormalizationLogTab />
            </RequirePlatformAdmin>
          }
        />
        <Route
          path="/admin/assessment-debug"
          element={
            <RequirePlatformAdmin>
              <AssessmentDebugPage />
            </RequirePlatformAdmin>
          }
        />
        <Route path="/settings/account" element={<SettingsPage />} />
        <Route path="/settings/team" element={<SettingsPage />} />
        <Route path="/settings/agents" element={<SettingsPage />} />
        <Route path="/settings/organisation" element={<OrgProfilePage />} />
        <Route path="/settings/technology" element={<OrgProfilePage />} />
        <Route path="/settings/domains" element={<OrgProfilePage />} />
        <Route path="/settings/uploads" element={<OrgProfilePage />} />
        <Route path="/settings/integrations" element={<IntegrationsPage />} />
      </Route>
      <Route
        path="/org/report"
        element={
          <ProtectedRoute>
            <ExecutiveReportPage />
          </ProtectedRoute>
        }
      />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/data-handling" element={<DataHandlingPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
    </>
  );
}

export default App;
