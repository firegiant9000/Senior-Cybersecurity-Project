import { Routes, Route } from 'react-router-dom';
import Dashboard from './Dashboard.tsx';
import LoginPage from './pages/LoginPage.tsx';
import SettingsPage from './pages/SettingsPage.tsx';
import ProtectedRoute from './components/ProtectedRoute.tsx';

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
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
