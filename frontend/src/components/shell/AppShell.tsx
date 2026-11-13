import React, { useEffect, useRef } from 'react';
import { Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useDarkMode } from '../../hooks/useDarkMode';
import { titleFor } from '../../config/pageTitles';
import { visibleNav, activeNav } from '../../config/navigation';
import DashboardHeader from '../dashboard/DashboardHeader';
import PrimaryNav from './PrimaryNav';
import SecondaryNav from './SecondaryNav';
import '../../Dashboard.css';
import './AppShell.css';

// Last pathname seen by any shell. Module-level because the two sibling layout routes in App.tsx
// each mount their own AppShell, so a per-instance ref resets when navigation crosses them.
let lastPathSeen: string | null = null;

/** Test-only: forget the last pathname so the next shell mount counts as the session's first. */
export function resetShellFocusForTests(): void {
  lastPathSeen = null;
}

export default function AppShell(): React.JSX.Element {
  const [dark, toggleDark] = useDarkMode();
  const { user, logout, orgId, role } = useAuth();
  const { pathname, search } = useLocation();
  const mainRef = useRef<HTMLElement | null>(null);
  const minimal = orgId == null;

  const groups = visibleNav({ role: role ?? null, orgId: orgId ?? null });
  const active = activeNav(pathname, search);
  // activeNav ignores visibility: only expose a group (and its items) the user can see.
  const visibleGroup = groups.find((g) => g.id === active.group?.id) ?? null;
  const activeGroupId = visibleGroup?.id ?? null;
  const sectionItems = visibleGroup?.items ?? [];
  const activeItemId = visibleGroup ? (active.item?.id ?? null) : null;

  useEffect(() => {
    document.title = `${titleFor(pathname, search)} · Hacker Tracker`;
  }, [pathname, search]);

  // Focus moves on path changes only (not tab changes within a page, not the session's first mount).
  // Comparing against the last pathname seen (not a first-run flag) keeps StrictMode's double
  // effect run harmless and survives AppShell remounting across sibling layout routes.
  useEffect(() => {
    if (lastPathSeen === pathname) return;
    const hadPrevious = lastPathSeen !== null;
    lastPathSeen = pathname;
    if (hadPrevious) mainRef.current?.focus();
  }, [pathname]);

  return (
    <div className="dashboard-container">
      <a className="skip-link" href="#main">Skip to content</a>
      <DashboardHeader dark={dark} onToggleDark={toggleDark} user={user} onLogout={logout} minimal={minimal} />
      {!minimal && (
        <>
          <PrimaryNav groups={groups} activeGroupId={activeGroupId} activeItemId={activeItemId} />
          <SecondaryNav items={sectionItems} activeItemId={activeItemId} />
        </>
      )}
      <main id="main" ref={mainRef} tabIndex={-1} className="dashboard-content">
        <Outlet />
      </main>
    </div>
  );
}
