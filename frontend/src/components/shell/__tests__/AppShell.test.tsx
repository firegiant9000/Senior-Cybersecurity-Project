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
  return <button onClick={() => navigate('/settings/account')}>go settings</button>;
}

function SearchButton() {
  const navigate = useNavigate();
  return <button onClick={() => navigate('/org/findings?x=2')}>go same path</button>;
}

function renderShell(initial: string) {
  return render(
    <MemoryRouter initialEntries={[initial]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/overview" element={<GoButton />} />
          <Route path="/org/findings" element={<p>findings page</p>} />
          <Route path="/org/assets/upload" element={<p>upload page</p>} />
          <Route path="/admin/pipeline" element={<p>pipeline page</p>} />
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
    renderShell('/overview');
    const primary = screen.getByRole('navigation', { name: 'Primary' });
    const links = within(primary).getAllByRole('link');
    expect(links.map((l) => l.textContent)).toEqual(['Overview', 'My organisation', 'Threat intelligence']);
    expect(links[1]).toHaveAttribute('href', '/org/assets');
    expect(links[2]).toHaveAttribute('href', '/intel/vulnerabilities');
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
  });

  it('marks the active group and item with aria-current and renders links as anchors', () => {
    renderShell('/org/findings');
    const group = screen.getByRole('link', { name: 'My organisation' });
    const item = screen.getByRole('link', { name: 'Findings' });
    expect(group).toHaveAttribute('aria-current', 'page');
    expect(item).toHaveAttribute('aria-current', 'page');
    expect(item).toHaveAttribute('href', '/org/findings');
    expect(screen.getByRole('link', { name: 'Assets' })).not.toHaveAttribute('aria-current');
    expect(screen.getByRole('link', { name: 'Overview' })).not.toHaveAttribute('aria-current');
    const section = screen.getByRole('navigation', { name: 'Section' });
    expect(within(section).getAllByRole('link').map((l) => l.textContent)).toEqual([
      'Assets', 'Findings', 'Vendor Alerts', 'Risk Profile', 'AI Briefing',
    ]);
  });

  it('renders no section nav on Overview', () => {
    renderShell('/overview');
    expect(screen.queryByRole('navigation', { name: 'Section' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Overview' })).toHaveAttribute('aria-current', 'page');
  });

  it('does not expose Admin items to a non-admin on /admin/pipeline', () => {
    renderShell('/admin/pipeline');
    expect(screen.queryByRole('link', { name: 'Admin' })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Pipeline Health' })).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation', { name: 'Section' })).not.toBeInTheDocument();
  });

  it('shows Admin to a platform admin', () => {
    authValue.role = 'admin';
    renderShell('/admin/pipeline');
    expect(screen.getByRole('link', { name: 'Admin' })).toHaveAttribute('aria-current', 'page');
    expect(screen.getByRole('link', { name: 'Pipeline Health' })).toHaveAttribute('aria-current', 'page');
  });

  it('lists every visible item in the mobile select and navigates on change', () => {
    renderShell('/overview');
    const select = screen.getByRole('combobox', { name: 'Navigate to page' });
    const labels = within(select).getAllByRole('option').map((o) => o.textContent);
    expect(labels).toContain('Overview');
    expect(labels).toContain('Findings');
    expect(labels).not.toContain('Pipeline Health');
    expect(labels).toContain('Vulnerabilities');
    expect(labels).not.toContain('Recent Vulnerabilities');
    fireEvent.change(select, { target: { value: '/org/findings' } });
    expect(screen.getByText('findings page')).toBeInTheDocument();
    expect(document.title).toBe('Findings · Hacker Tracker');
  });

  it('renders the seven avatar items then Log Out, and no Assessment Debug', () => {
    renderShell('/overview');
    expect(menuLabels()).toEqual([
      'Organisation profile', 'Team and agents', 'Integrations', 'Account',
      'Glossary', 'Privacy', 'Data handling', 'Log Out',
    ]);
  });

  it('shows a disabled placeholder in the mobile select on a page outside the nav, and Overview is selectable', () => {
    render(
      <MemoryRouter initialEntries={['/settings/account']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/settings/account" element={<p>settings page</p>} />
            <Route path="/overview" element={<p>dash page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    const select = screen.getByRole('combobox', { name: 'Navigate to page' });
    expect(select).toHaveValue('');
    expect(within(select).getByRole('option', { name: 'Choose a page' })).toBeDisabled();
    fireEvent.change(select, { target: { value: '/overview' } });
    expect(screen.getByText('dash page')).toBeInTheDocument();
  });

  it('gives an org admin the same avatar items and no Assessment Debug', () => {
    authValue.orgRole = 'admin';
    renderShell('/overview');
    const labels = menuLabels();
    expect(labels).toEqual([
      'Organisation profile', 'Team and agents', 'Integrations', 'Account',
      'Glossary', 'Privacy', 'Data handling', 'Log Out',
    ]);
    expect(labels).not.toContain('Assessment Debug');
  });

  it('renders no nav at all without an organisation', () => {
    authValue.orgId = null;
    renderShell('/overview');
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
            <Route path="/settings/account" element={<p>settings page</p>} />
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
    renderShell('/overview');
    fireEvent.click(screen.getByRole('button', { name: 'Open profile menu' }));
    expect(screen.getByRole('menuitem', { name: 'Log Out' })).toBeInTheDocument();
    expect(screen.getAllByRole('menuitem')).toHaveLength(1);
    expect(screen.queryByRole('menuitem', { name: 'Account' })).not.toBeInTheDocument();
    expect(screen.getByText('member@example.com', { selector: '.email' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Open glossary' })).not.toBeInTheDocument();
  });

  it('shows the full menu and glossary button with an organisation', () => {
    renderShell('/overview');
    fireEvent.click(screen.getByRole('button', { name: 'Open profile menu' }));
    expect(screen.getByRole('menuitem', { name: 'Account' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Open glossary' })).toBeInTheDocument();
  });

  it('renders a skip link to #main', () => {
    renderShell('/overview');
    expect(screen.getByText('Skip to content')).toHaveAttribute('href', '#main');
  });

  it('renders the main landmark with id="main"', () => {
    renderShell('/overview');
    const main = screen.getByRole('main');
    expect(main).toHaveAttribute('id', 'main');
    expect(main).toHaveAttribute('tabindex', '-1');
    expect(main).toContainElement(screen.getByText('go glossary'));
  });

  it('sets the document title from the path', () => {
    renderShell('/org/findings');
    expect(document.title).toBe('Findings · Hacker Tracker');
  });

  it('titles a hidden Admin URL as not found for a member', () => {
    renderShell('/admin/pipeline');
    expect(document.title).toBe('Page not found · Hacker Tracker');
  });

  it('titles the Admin URL normally for a platform admin', () => {
    authValue.role = 'admin';
    renderShell('/admin/pipeline');
    expect(document.title).toBe('Pipeline Health · Hacker Tracker');
  });

  it('moves focus to main on navigation but not on first mount', () => {
    renderShell('/overview');
    expect(document.activeElement).not.toBe(screen.getByRole('main'));
    fireEvent.click(screen.getByText('go glossary'));
    expect(screen.getByText('glossary page')).toBeInTheDocument();
    expect(document.activeElement).toBe(screen.getByRole('main'));
    expect(document.title).toBe('Glossary · Hacker Tracker');
  });

  it('does not focus main on initial load under StrictMode', () => {
    render(
      <React.StrictMode>
        <MemoryRouter initialEntries={['/overview']}>
          <Routes>
            <Route element={<AppShell />}>
              <Route path="/overview" element={<p>dash</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </React.StrictMode>,
    );
    expect(document.activeElement).not.toBe(screen.getByRole('main'));
  });

  it('keeps the title and focus on a search-only change', () => {
    render(
      <MemoryRouter initialEntries={['/org/findings?x=1']}>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/org/findings" element={<SearchButton />} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(document.title).toBe('Findings · Hacker Tracker');
    fireEvent.click(screen.getByText('go same path'));
    expect(document.title).toBe('Findings · Hacker Tracker');
    expect(document.activeElement).not.toBe(screen.getByRole('main'));
  });

  it('calls the dark mode toggle from the header theme button', () => {
    renderShell('/overview');
    fireEvent.click(screen.getByTitle('Toggle dark mode'));
    expect(mockToggle).toHaveBeenCalledTimes(1);
  });

  it('calls logout from the Log Out menu item', async () => {
    renderShell('/overview');
    fireEvent.click(screen.getByRole('button', { name: 'Open profile menu' }));
    fireEvent.click(screen.getByRole('menuitem', { name: 'Log Out' }));
    expect(mockLogout).toHaveBeenCalledTimes(1);
    // the header navigates to "/" after logout; wait for that to settle
    expect(await screen.findByText('home')).toBeInTheDocument();
  });
});

describe('titleFor', () => {
  it('resolves nav groups and items from the path', () => {
    expect(titleFor('/org/findings')).toBe('Findings');
    expect(titleFor('/org/vendor-alerts')).toBe('Vendor Alerts');
    expect(titleFor('/org/risk')).toBe('Risk Profile');
    expect(titleFor('/intel/vulnerabilities')).toBe('Vulnerabilities');
    expect(titleFor('/overview')).toBe('Overview');
  });

  it('uses the static map for other paths', () => {
    expect(titleFor('/settings/account')).toBe('Settings');
    expect(titleFor('/settings/team')).toBe('Settings');
    expect(titleFor('/admin/assessment-debug')).toBe('Assessment Debug');
    expect(titleFor('/settings/organisation')).toBe('Organisation profile');
    expect(titleFor('/glossary')).toBe('Glossary');
    expect(titleFor('/org/assets/upload')).toBe('Upload inventory');
    expect(titleFor('/settings/integrations')).toBe('Integrations');
    expect(titleFor('/onboarding')).toBe('Set up your organisation');
    expect(titleFor('/invites/abc')).toBe('Organisation invite');
    expect(titleFor('/nowhere')).toBe('Hacker Tracker');
  });
});
