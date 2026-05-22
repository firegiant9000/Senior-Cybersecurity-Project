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
import AssetsPage from "./pages/AssetsPage.tsx";
import IntegrationsPage from "./pages/IntegrationsPage.tsx";
import ProtectedRoute from "./components/ProtectedRoute.tsx";
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
        path="/onboarding"
        element={
          <ProtectedRoute requireOrg={false}>
            <AssessmentIntakePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/invites/:token"
        element={
          <ProtectedRoute requireOrg={false}>
            <AcceptInvitePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings/assessment-debug"
        element={
          <ProtectedRoute>
            <AssessmentDebugPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/assessment-intake"
        element={
          <ProtectedRoute requireOrg={false}>
            <AssessmentIntakePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/org-profile"
        element={
          <ProtectedRoute>
            <OrgProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/report/executive"
        element={
          <ProtectedRoute>
            <ExecutiveReportPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/glossary"
        element={
          <ProtectedRoute requireOrg={false}>
            <GlossaryPage />
          </ProtectedRoute>
        }
      />
      <Route path="/privacy" element={<PrivacyPage />} />
      <Route path="/data-handling" element={<DataHandlingPage />} />
      <Route
        path="/inventory/upload"
        element={
          <ProtectedRoute>
            <UploadInventoryPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/assets"
        element={
          <ProtectedRoute>
            <AssetsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/integrations"
        element={
          <ProtectedRoute>
            <IntegrationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/*"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
    </Routes>
    </>
  );
}

export default App;
