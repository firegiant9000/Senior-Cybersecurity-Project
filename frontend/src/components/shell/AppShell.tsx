import React, { useEffect, useRef } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useDarkMode } from '../../hooks/useDarkMode';
import { titleFor } from '../../config/pageTitles';
import DashboardHeader from '../dashboard/DashboardHeader';
import './AppShell.css';

export default function AppShell(): React.JSX.Element {
  const [dark, toggleDark] = useDarkMode();
  const { user, logout } = useAuth();
  const { pathname, search } = useLocation();
  const mainRef = useRef<HTMLElement | null>(null);
  const firstRun = useRef(true);

  useEffect(() => {
    document.title = `${titleFor(pathname, search)} · Hacker Tracker`;
  }, [pathname, search]);

  // Focus moves on path changes only (not tab changes within a page, not first mount).
  useEffect(() => {
    if (firstRun.current) {
      firstRun.current = false;
      return;
    }
    mainRef.current?.focus();
  }, [pathname]);

  return (
    <div className="dashboard-container">
      <a className="skip-link" href="#main">Skip to content</a>
      <DashboardHeader dark={dark} onToggleDark={toggleDark} user={user} onLogout={logout} />
      <main id="main" ref={mainRef} tabIndex={-1} className="dashboard-content">
        <Outlet />
      </main>
    </div>
  );
}
