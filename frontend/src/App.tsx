import { Routes, Route, Navigate } from "react-router-dom";
import Dashboard from "./Dashboard.tsx";
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
import ProtectedRoute from "./components/ProtectedRoute.tsx";
import AppShell from "./components/shell/AppShell.tsx";
import DemoBanner from "./components/DemoBanner.tsx";
import { useAuth } from "./context/AuthContext.tsx";


function RootRoute() {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (user) return <Navigate to="/dashboard" replace />;
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
      <Route path="/assessment-intake" element={<Navigate to="/onboarding" replace />} />
      <Route
        element={
          <ProtectedRoute>
            <AppShell />
          </ProtectedRoute>
        }
      >
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/settings/assessment-debug" element={<AssessmentDebugPage />} />
        <Route path="/org-profile" element={<OrgProfilePage />} />
        <Route path="/inventory/upload" element={<UploadInventoryPage />} />
        <Route path="/integrations" element={<IntegrationsPage />} />
      </Route>
      <Route
        path="/report/executive"
        element={
          <ProtectedRoute>
            <ExecutiveReportPage />
          </ProtectedRoute>
        }
      />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/data-handling" element={<DataHandlingPage />} />
      <Route path="/assets" element={<Navigate to="/dashboard?tab=assets" replace />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
    </>
  );
}

export default App;
