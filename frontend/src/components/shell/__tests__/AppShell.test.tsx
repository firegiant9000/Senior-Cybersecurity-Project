import React from 'react';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import AppShell, { resetShellFocusForTests } from '../AppShell';
import { titleFor } from '../../../config/pageTitles';

const mockToggle = vi.fn();
const mockLogout = vi.fn(async () => {});
const stableUser = { email: 'member@example.com' };
const authValue = {
  user: stableUser,
  logout: mockLogout,
  role: null as string | null,
  orgRole: 'member' as string | null,
  orgId: 1 as number | null,
};

vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => authValue,
}));

vi.mock('../../../hooks/useDarkMode', () => ({
  useDarkMode: () => [false, mockToggle],
}));

function GoButton() {
  const navigate = useNavigate();
  return <button onClick={() => navigate('/glossary')}>go glossary</button>;
}

function CrossButton() {
  const navigate = useNavigate();
  return <button onClick={() => navigate('/settings')}>go settings</button>;
}

function SearchButton() {
  const navigate = useNavigate();
  return <button onClick={() => navigate('/dashboard?tab=vendorAlerts')}>go vendor</button>;
}

function renderShell(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/dashboard" element={<GoButton />} />
          <Route path="/glossary" element={<p>glossary page</p>} />
          <Route path="/" element={<p>home</p>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('AppShell', () => {
  beforeEach(() => {
    mockToggle.mockClear();
    mockLogout.mockClear();
    document.title = '';
    resetShellFocusForTests();
    authValue.orgId = 1;
    authValue.orgRole = 'member';
    authValue.role = null;
  });

  function menuLabels(): string[] {
    fireEvent.click(screen.getByRole('button', { name: 'Open profile menu' }));
    return screen.getAllByRole('menuitem').map((el) => el.textContent ?? '');
  }

  it('shows three primary links and no Admin for a member', () => {
    renderShell('/dashboard');
    const primary = screen.getByRole('navigation', { name: 'Primary' });
    const links = within(primary).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Overview', 'My organisation', 'Threat intelligence']);
    expect(links[1]).toHaveAttribute('href', '/dashboard?tab=assets');
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
  });

  it('marks the active group and item with aria-current and renders links as anchors', () => {
    renderShell('/dashboard?tab=assessment&sub=findings');
    const group = screen.getByRole('link', { name: 'My organisation' });
    const item = screen.getByRole('link', { name: 'Findings' });
    expect(group).toHaveAttribute('aria-current', 'page');
    expect(item).toHaveAttribute('aria-current', 'page');
    expect(item).toHaveAttribute('href', '/dashboard?tab=assessment&sub=findings');
    expect(screen.getByRole('link', { name: 'Assets' })).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current');
    const section = screen.getByRole('navigation', { name: 'Section' });
    expect(within(section).getAllByRole('link').map((l) => l.textContent)).toEqual([
      'Assets', 'Findings', 'Vendor Alerts', 'Risk Profile', 'AI Briefing',
    ]);
  });

  it('renders no section nav on Overview', () => {
    renderShell('/dashboard');
    expect(screen.queryByRole('navigation', { name: 'Section' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page');
  });

  it('does not expose Admin items to a non-admin on ?tab=admin', () => {
    renderShell('/dashboard?tab=admin');
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Pipeline Health' })).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Section' })).not.toBeInTheDocument();
  });

  it('shows Admin to a platform admin', () => {
    authValue.role = 'admin';
    renderShell('/dashboard?tab=admin&sub=pipelineHealth');
    expect(screen.getByRole('link', { name: 'Admin' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Pipeline Health' })).toHaveAttribute('aria-current', 'page');
  });

  it('lists every visible item in the mobile select and navigates on change', () => {
    renderShell('/dashboard');
    const select = screen.getByRole('combobox', { name: 'Navigate to page' });
    const labels = within(select).getAllByRole('option').map((o) => o.textContent);
    expect(labels).toContain('Overview');
    expect(labels).toContain('Findings');
    expect(labels).not.toContain('Pipeline Health');
    fireEvent.change(select, { target: { value: '/dashboard?tab=vendorAlerts' } });
    expect(document.title).toBe('Vendor Alerts · Hacker Tracker');
  });

  it('renders the seven avatar items then Log Out, and no Assessment Debug', () => {
    renderShell('/dashboard');
    expect(menuLabels()).toEqual([
      'Organisation profile', 'Team and agents', 'Integrations', 'Account',
      'Glossary', 'Privacy', 'Data handling', 'Log Out',
    ]);
  });

  it('shows a disabled placeholder in the mobile select on a page outside the nav, and Overview is selectable', () => {
    render(
      <MemoryRouter initialEntries={['/settings']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/settings" element={<p>settings page</p>} />
            <Route path="/dashboard" element={<p>dash page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    const select = screen.getByRole('combobox', { name: 'Navigate to page' });
    expect(select).toHaveValue('');
    expect(within(select).getByRole('option', { name: 'Choose a page' })).toBeDisabled();
    fireEvent.change(select, { target: { value: '/dashboard' } });
    expect(screen.getByText('dash page')).toBeInTheDocument();
  });

  it('gives an org admin the same avatar items and no Assessment Debug', () => {
    authValue.orgRole = 'admin';
    renderShell('/dashboard');
    const labels = menuLabels();
    expect(labels).toEqual([
      'Organisation profile', 'Team and agents', 'Integrations', 'Account',
      'Glossary', 'Privacy', 'Data handling', 'Log Out',
    ]);
    expect(labels).not.toContain('Assessment Debug');
  });

  it('renders no nav at all without an organisation', () => {
    authValue.orgId = null;
    renderShell('/dashboard');
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  it('moves focus to main when navigation crosses sibling layout routes', () => {
    render(
      <MemoryRouter initialEntries={['/glossary']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/glossary" element={<CrossButton />} />
          </Route>
          <Route element={<AppShell />}>
            <Route path="/settings" element={<p>settings page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(document.activeElement).not.toBe(screen.getByRole('main'));
    fireEvent.click(screen.getByText('go settings'));
    expect(screen.getByText('settings page')).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole('main'));
  });

  it('shows a minimal menu (email, role, Log Out only) and no glossary button without an organisation', () => {
    authValue.orgId = null;
    authValue.orgRole = null;
    renderShell('/dashboard');
    fireEvent.click(screen.getByRole('button', { name: 'Open profile menu' }));
    expect(screen.getByRole('menuitem', { name: 'Log Out' })).toBeInTheDocument();
    expect(screen.getAllByRole('menuitem')).toHaveLength(1);
    expect(screen.queryByRole('menuitem', { name: 'Account' })).not.toBeInTheDocument();
    expect(screen.getByText('member@example.com', { selector: '.email' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Open glossary' })).not.toBeInTheDocument();
  });

  it('shows the full menu and glossary button with an organisation', () => {
    renderShell('/dashboard');
    fireEvent.click(screen.getByRole('button', { name: 'Open profile menu' }));
    expect(screen.getByRole('menuitem', { name: 'Account' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open glossary' })).toBeInTheDocument();
  });

  it('renders a skip link to #main', () => {
    renderShell('/dashboard');
    expect(screen.getByText('Skip to content')).toHaveAttribute('href', '#main');
  });

  it('renders the main landmark with id="main"', () => {
    renderShell('/dashboard');
    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main');
    expect(main).toHaveAttribute('tabindex', '-1');
    expect(main).toContainElement(screen.getByText('go glossary'));
  });

  it('sets the document title from the dashboard sub-tab', () => {
    renderShell('/dashboard?tab=assessment&sub=findings');
    expect(document.title).toBe('Findings · Hacker Tracker');
  });

  it('titles a hidden Admin URL as not found for a member', () => {
    renderShell('/dashboard?tab=admin');
    expect(document.title).toBe('Page not found · Hacker Tracker');
  });

  it('titles the Admin URL normally for a platform admin', () => {
    authValue.role = 'admin';
    renderShell('/dashboard?tab=admin');
    expect(document.title).toBe('Pipeline Health · Hacker Tracker');
  });

  it('moves focus to main on navigation but not on first mount', () => {
    renderShell('/dashboard');
    expect(document.activeElement).not.toBe(screen.getByRole('main'));
    fireEvent.click(screen.getByText('go glossary'));
    expect(screen.getByText('glossary page')).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole('main'));
    expect(document.title).toBe('Glossary · Hacker Tracker');
  });

  it('does not focus main on initial load under StrictMode', () => {
    render(
      <React.StrictMode>
        <MemoryRouter initialEntries={['/dashboard']}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/dashboard" element={<p>dash</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </React.StrictMode>,
    );
    expect(document.activeElement).not.toBe(screen.getByRole('main'));
  });

  it('updates the title but keeps focus on a search-only change', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard?tab=assessment&sub=findings']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/dashboard" element={<SearchButton />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(document.title).toBe('Findings · Hacker Tracker');
    fireEvent.click(screen.getByText('go vendor'));
    expect(document.title).toBe('Vendor Alerts · Hacker Tracker');
    expect(document.activeElement).not.toBe(screen.getByRole('main'));
  });

  it('calls the dark mode toggle from the header theme button', () => {
    renderShell('/dashboard');
    fireEvent.click(screen.getByTitle('Toggle dark mode'));
    expect(mockToggle).toHaveBeenCalledTimes(1);
  });

  it('calls logout from the Log Out menu item', async () => {
    renderShell('/dashboard');
    fireEvent.click(screen.getByRole('button', { name: 'Open profile menu' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Log Out' }));
    expect(mockLogout).toHaveBeenCalledTimes(1);
    // the header navigates to "/" after logout; wait for that to settle
    expect(await screen.findByText('home')).toBeInTheDocument();
  });
});

describe('titleFor', () => {
  it('resolves dashboard sub-tabs, groups and legacy flat ids', () => {
    expect(titleFor('/dashboard', '?tab=assessment&sub=findings')).toBe('Findings');
    expect(titleFor('/dashboard', '?tab=findings')).toBe('Findings');
    expect(titleFor('/dashboard', '?tab=vendorAlerts')).toBe('Vendor Alerts');
    expect(titleFor('/dashboard', '?tab=assessment')).toBe('Risk Profile');
    expect(titleFor('/dashboard', '')).toBe('Overview');
    expect(titleFor('/dashboard', '?tab=nope&x=1')).toBe('Overview');
  });

  it('uses the static map for other paths', () => {
    expect(titleFor('/settings', '')).toBe('Settings');
    expect(titleFor('/settings/assessment-debug', '')).toBe('Assessment Debug');
    expect(titleFor('/org-profile', '')).toBe('Organisation profile');
    expect(titleFor('/glossary', '')).toBe('Glossary');
    expect(titleFor('/assets', '')).toBe('Upload inventory');
    expect(titleFor('/inventory/upload', '')).toBe('Upload inventory');
    expect(titleFor('/integrations', '')).toBe('Integrations');
    expect(titleFor('/onboarding', '')).toBe('Set up your organisation');
    expect(titleFor('/invites/abc', '')).toBe('Organisation invite');
    expect(titleFor('/nowhere', '')).toBe('Hacker Tracker');
  });
});
