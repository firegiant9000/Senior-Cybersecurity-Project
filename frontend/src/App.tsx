import { Routes, Route } from 'react-router-dom';
import Dashboard from './Dashboard.tsx';
import LoginPage from './pages/LoginPage.tsx';
import OnboardingPage from './pages/OnboardingPage.tsx';
import SettingsPage from './pages/SettingsPage.tsx';
import ProtectedRoute from './components/ProtectedRoute.tsx';
import { useAuth } from './context/AuthContext.tsx';

function App() {
  const { refreshProfile } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/onboarding"
        element={
          <ProtectedRoute requireOrg={false}>
            <OnboardingPage onComplete={refreshProfile} />
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
        path="/*"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
    </Routes>
  );
}

export default App;
