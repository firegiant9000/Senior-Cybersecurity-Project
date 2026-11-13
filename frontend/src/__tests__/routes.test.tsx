import { render, screen, waitFor, cleanup, configure } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { resetShellFocusForTests } from '../components/shell/AppShell'

// Screens are lazy-loaded behind one Suspense; under a full parallel run a cold dynamic
// import can take longer than the 1 s default. File-scoped (Vitest isolates test files).
configure({ asyncUtilTimeout: 5000 })

// Route-level tests: <App /> in a MemoryRouter, every screen a data-testid stub,
// ProtectedRoute / AppShell / LegacyRedirect / RequirePlatformAdmin real.

const mockAuthContext = {
  user: null as unknown,
  loading: false,
  orgId: null as number | null,
  orgLoading: false,
  profileError: false,
  emailUnverified: false,
  signedOutDeliberately: false,
  role: null as string | null,
  orgRole: null as string | null,
  refreshProfile: vi.fn(),
  login: vi.fn(),
  signup: vi.fn(),
  logout: vi.fn(),
  getIdToken: vi.fn(),
}

vi.mock('../context/AuthContext.tsx', () => ({
  useAuth: () => mockAuthContext,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('../context/AuthContext', () => ({
  useAuth: () => mockAuthContext,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('../hooks/useDarkMode', () => ({
  useDarkMode: () => [false, vi.fn()],
}))

vi.mock('../components/DemoBanner.tsx', () => ({ default: () => null }))

const { stub } = vi.hoisted(() => ({
  stub: async (id: string) => {
    const React = await import('react')
    return { default: () => React.createElement('div', { 'data-testid': id }, id) }
  },
}))

vi.mock('../pages/LoginPage.tsx', () => stub('login-page'))
vi.mock('../pages/LandingPage.tsx', () => stub('landing-page'))
vi.mock('../pages/settings/pages.tsx', async () => {
  const React = await import('react')
  const page = (id: string) => () => React.createElement('div', { 'data-testid': id }, id)
  return {
    AccountPage: page('account-page'),
    OrganisationPage: page('organisation-page'),
    TechnologyPage: page('technology-page'),
    DomainsPage: page('domains-page'),
    UploadsPage: page('uploads-page'),
    TeamPage: page('team-page'),
    AgentsPage: page('agents-page'),
  }
})
vi.mock('../pages/AssessmentDebugPage.tsx', () => stub('assessment-debug-page'))
vi.mock('../pages/AssessmentIntakePage.tsx', () => stub('onboarding-page'))
vi.mock('../pages/AcceptInvitePage.tsx', () => stub('accept-invite-page'))
vi.mock('../pages/ExecutiveReportPage.tsx', () => stub('executive-report-page'))
vi.mock('../pages/GlossaryPage.tsx', () => stub('glossary-page'))
vi.mock('../pages/PrivacyPage.tsx', () => stub('privacy-page'))
vi.mock('../pages/DataHandlingPage.tsx', () => stub('data-handling-page'))
vi.mock('../pages/UploadInventoryPage.tsx', () => stub('upload-inventory-page'))
vi.mock('../pages/NotFoundPage', () => stub('not-found-page'))
vi.mock('../pages/NotFoundPage.tsx', () => stub('not-found-page'))
vi.mock('../pages/IntegrationsPage.tsx', () => stub('integrations-page'))
vi.mock('../pages/OverviewPage.tsx', () => stub('overview-page'))
vi.mock('../pages/AssetsPage', () => stub('assets-page'))
vi.mock('../components/tabs/TrendsTab', () => stub('trends-tab'))
vi.mock('../components/tabs/PipelineHealthTab', () => stub('pipeline-health-tab'))
vi.mock('../components/tabs/NormalizationLogTab', () => stub('normalization-log-tab'))
vi.mock('../components/tabs/SmBAdvisorTab', () => stub('smb-advisor-tab'))
vi.mock('../components/tabs/VendorAlertsTab', () => stub('vendor-alerts-tab'))
vi.mock('../components/tabs/DataSourcesTab', () => stub('data-sources-tab'))
vi.mock('../components/tabs/FindingsTab', () => stub('findings-tab'))
vi.mock('../components/tabs/AISummaryTab', () => stub('ai-summary-tab'))
vi.mock('../components/tabs/AnomaliesTab', () => stub('anomalies-tab'))
vi.mock('../components/intel/VulnerabilitiesScreen', () => stub('vulnerabilities-screen'))

// Import after all mocks
import App from '../App'

function LocationProbe() {
  const { pathname, search, hash } = useLocation()
  return (
    <>
      <div data-testid="probe-pathname">{pathname}</div>
      <div data-testid="probe-search">{search}</div>
      <div data-testid="probe-hash">{hash}</div>
    </>
  )
}

function renderApp(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <App />
      <LocationProbe />
    </MemoryRouter>,
  )
}

const signedIn = (over: Partial<typeof mockAuthContext> = {}) => {
  Object.assign(mockAuthContext, {
    user: { uid: 'u1', email: 'user@example.com' },
    orgId: 1,
    role: 'admin',
    orgRole: 'admin',
    ...over,
  })
}

const pathname = () => screen.getByTestId('probe-pathname').textContent
const search = () => screen.getByTestId('probe-search').textContent
const hash = () => screen.getByTestId('probe-hash').textContent

// Every path from Task 5A.1 -> its stub. `inMain` is false only for the report.
const PATHS: Array<[string, string, boolean]> = [
  ['/overview', 'overview-page', true],
  ['/org/assets', 'assets-page', true],
  ['/org/assets/upload', 'upload-inventory-page', true],
  ['/org/findings', 'findings-tab', true],
  ['/org/vendor-alerts', 'vendor-alerts-tab', true],
  ['/org/risk', 'smb-advisor-tab', true],
  ['/org/briefing', 'ai-summary-tab', true],
  ['/intel/vulnerabilities', 'vulnerabilities-screen', true],
  ['/intel/anomalies/ic3', 'anomalies-tab', true],
  ['/intel/trends', 'trends-tab', true],
  ['/intel/reference/ic3', 'data-sources-tab', true],
  ['/admin/pipeline', 'pipeline-health-tab', true],
  ['/admin/normalization-log', 'normalization-log-tab', true],
  ['/admin/assessment-debug', 'assessment-debug-page', true],
  ['/settings/account', 'account-page', true],
  ['/settings/team', 'team-page', true],
  ['/settings/agents', 'agents-page', true],
  ['/settings/organisation', 'organisation-page', true],
  ['/settings/technology', 'technology-page', true],
  ['/settings/domains', 'domains-page', true],
  ['/settings/uploads', 'uploads-page', true],
  ['/settings/integrations', 'integrations-page', true],
  ['/org/report', 'executive-report-page', false],
]

// The eight settings paths, each inside the settings nav.
const SETTINGS_PATHS: Array<[string, string]> = [
  ['/settings/account', 'account-page'],
  ['/settings/organisation', 'organisation-page'],
  ['/settings/technology', 'technology-page'],
  ['/settings/domains', 'domains-page'],
  ['/settings/uploads', 'uploads-page'],
  ['/settings/team', 'team-page'],
  ['/settings/agents', 'agents-page'],
  ['/settings/integrations', 'integrations-page'],
]

// Legacy table (Task 2G): [input URL, final pathname, stub, final search, final hash]
const LEGACY: Array<[string, string, string, string, string]> = [
  ['/dashboard', '/overview', 'overview-page', '', ''],
  ['/dashboard/', '/overview', 'overview-page', '', ''],
  ['/dashboard?tab=overview', '/overview', 'overview-page', '', ''],
  ['/dashboard?tab=assessment', '/org/risk', 'smb-advisor-tab', '', ''],
  ['/dashboard?tab=assessment&sub=smbAdvisor', '/org/risk', 'smb-advisor-tab', '', ''],
  ['/dashboard?tab=smbAdvisor', '/org/risk', 'smb-advisor-tab', '', ''],
  ['/dashboard?tab=assessment&sub=nope', '/org/risk', 'smb-advisor-tab', '', ''],
  ['/dashboard?tab=assessment&sub=findings', '/org/findings', 'findings-tab', '', ''],
  ['/dashboard?tab=findings', '/org/findings', 'findings-tab', '', ''],
  ['/dashboard?tab=assessment&sub=aiSummary', '/org/briefing', 'ai-summary-tab', '', ''],
  ['/dashboard?tab=aiSummary', '/org/briefing', 'ai-summary-tab', '', ''],
  ['/dashboard?tab=vendorAlerts', '/org/vendor-alerts', 'vendor-alerts-tab', '', ''],
  ['/dashboard?tab=assets', '/org/assets', 'assets-page', '', ''],
  ['/dashboard?tab=threats', '/intel/vulnerabilities', 'vulnerabilities-screen', '', ''],
  ['/dashboard?tab=threats&sub=threatIntel', '/intel/vulnerabilities', 'vulnerabilities-screen', '', ''],
  ['/dashboard?tab=threatIntel', '/intel/vulnerabilities', 'vulnerabilities-screen', '', ''],
  ['/dashboard?tab=threats&sub=nope', '/intel/vulnerabilities', 'vulnerabilities-screen', '', ''],
  ['/dashboard?tab=threats&sub=riskScoring', '/intel/vulnerabilities', 'vulnerabilities-screen', '?source=scored', ''],
  ['/dashboard?tab=riskScoring', '/intel/vulnerabilities', 'vulnerabilities-screen', '?source=scored', ''],
  ['/dashboard?tab=threats&sub=anomalies', '/intel/anomalies/ic3', 'anomalies-tab', '', ''],
  ['/dashboard?tab=anomalies', '/intel/anomalies/ic3', 'anomalies-tab', '', ''],
  ['/dashboard?tab=trendsData', '/intel/trends', 'trends-tab', '', ''],
  ['/dashboard?tab=trendsData&sub=trends', '/intel/trends', 'trends-tab', '', ''],
  ['/dashboard?tab=trends', '/intel/trends', 'trends-tab', '', ''],
  ['/dashboard?tab=trendsData&sub=dataSources', '/intel/reference/ic3', 'data-sources-tab', '', ''],
  ['/dashboard?tab=dataSources', '/intel/reference/ic3', 'data-sources-tab', '', ''],
  ['/dashboard?tab=admin', '/admin/pipeline', 'pipeline-health-tab', '', ''],
  ['/dashboard?tab=admin&sub=pipelineHealth', '/admin/pipeline', 'pipeline-health-tab', '', ''],
  ['/dashboard?tab=pipelineHealth', '/admin/pipeline', 'pipeline-health-tab', '', ''],
  ['/dashboard?tab=admin&sub=normalizationLog', '/admin/normalization-log', 'normalization-log-tab', '', ''],
  ['/dashboard?tab=normalizationLog', '/admin/normalization-log', 'normalization-log-tab', '', ''],
  ['/dashboard?tab=nope&x=1', '/overview', 'overview-page', '', ''],
  ['/assets', '/org/assets', 'assets-page', '', ''],
  ['/inventory/upload', '/org/assets/upload', 'upload-inventory-page', '', ''],
  ['/integrations', '/settings/integrations', 'integrations-page', '', ''],
  ['/integrations?m365=connected&message=x', '/settings/integrations', 'integrations-page', '?m365=connected&message=x', ''],
  ['/report/executive?autoprint=1', '/org/report', 'executive-report-page', '?autoprint=1', ''],
  ['/settings', '/settings/account', 'account-page', '', ''],
  ['/Settings', '/settings/account', 'account-page', '', ''],
  ['/settings/assessment-debug', '/admin/assessment-debug', 'assessment-debug-page', '', ''],
  ['/org-profile', '/settings/organisation', 'organisation-page', '', ''],
  ['/org-profile#section-security-profile', '/settings/organisation', 'organisation-page', '', '#security-profile'],
  ['/org-profile#section-vendors', '/settings/technology', 'technology-page', '', ''],
  ['/org-profile#section-domains', '/settings/domains', 'domains-page', '', ''],
  ['/org-profile#section-uploads', '/settings/uploads', 'uploads-page', '', ''],
  ['/assessment-intake', '/onboarding', 'onboarding-page', '', ''],
  ['/intel/anomalies', '/intel/anomalies/ic3', 'anomalies-tab', '', ''],
  ['/intel/reference', '/intel/reference/ic3', 'data-sources-tab', '', ''],
]

describe('routes', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resetShellFocusForTests()
    document.title = ''
    Object.assign(mockAuthContext, {
      user: null,
      loading: false,
      orgId: null,
      orgLoading: false,
      profileError: false,
      emailUnverified: false,
      signedOutDeliberately: false,
      role: null,
      orgRole: null,
    })
  })

  afterEach(() => cleanup())

  describe('every path renders its screen', () => {
    it.each(PATHS)('%s -> %s', async (path, testId, inMain) => {
      signedIn()
      const { container } = renderApp(path)
      const el = await screen.findByTestId(testId)
      const main = container.querySelector('#main')
      if (inMain) {
        expect(main).not.toBeNull()
        expect(main!.contains(el)).toBe(true)
      } else {
        expect(container.querySelector('#main')).toBeNull()
      }
      expect(pathname()).toBe(path)
    })
  })

  describe('settings paths render inside the settings nav', () => {
    it.each(SETTINGS_PATHS)('%s -> %s inside main, nav marks it current', async (path, testId) => {
      signedIn()
      const { container } = renderApp(path)
      const el = await screen.findByTestId(testId)
      const main = container.querySelector('#main')
      expect(main).not.toBeNull()
      expect(main!.contains(el)).toBe(true)
      const nav = screen.getByRole('navigation', { name: 'Settings' })
      expect(main!.contains(nav)).toBe(true)
      const current = nav.querySelectorAll('a[aria-current="page"]')
      expect(current).toHaveLength(1)
      expect(current[0].getAttribute('href')).toBe(path)
    })
  })

  describe('legacy URLs redirect end to end', () => {
    it.each(LEGACY)('%s -> %s', async (from, to, testId, toSearch, toHash) => {
      signedIn()
      renderApp(from)
      await screen.findByTestId(testId)
      expect(pathname()).toBe(to)
      expect(search()).toBe(toSearch)
      expect(hash()).toBe(toHash)
    })
  })

  describe('platform admin guard', () => {
    it('/admin/pipeline as an org admin without platform role is not found', async () => {
      signedIn({ role: null, orgRole: 'admin' })
      renderApp('/admin/pipeline')
      expect(await screen.findByTestId('not-found-page')).toBeInTheDocument()
      expect(screen.queryByTestId('pipeline-health-tab')).not.toBeInTheDocument()
    })

    it('/dashboard?tab=admin as an org admin without platform role is not found', async () => {
      signedIn({ role: null, orgRole: 'admin' })
      renderApp('/dashboard?tab=admin')
      expect(await screen.findByTestId('not-found-page')).toBeInTheDocument()
      expect(pathname()).toBe('/admin/pipeline')
      expect(screen.queryByTestId('pipeline-health-tab')).not.toBeInTheDocument()
    })

    it('/admin/pipeline as a platform admin renders the pipeline screen', async () => {
      signedIn({ role: 'admin' })
      renderApp('/admin/pipeline')
      expect(await screen.findByTestId('pipeline-health-tab')).toBeInTheDocument()
    })
  })

  describe('no organisation', () => {
    it('/org/findings goes to onboarding', async () => {
      signedIn({ orgId: null })
      renderApp('/org/findings')
      expect(await screen.findByTestId('onboarding-page')).toBeInTheDocument()
      expect(pathname()).toBe('/onboarding')
    })

    it('/settings/team goes to onboarding', async () => {
      signedIn({ orgId: null })
      renderApp('/settings/team')
      expect(await screen.findByTestId('onboarding-page')).toBeInTheDocument()
      expect(pathname()).toBe('/onboarding')
    })

    it('/glossary renders with no navigation', async () => {
      signedIn({ orgId: null })
      renderApp('/glossary')
      expect(await screen.findByTestId('glossary-page')).toBeInTheDocument()
      expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
    })
  })

  describe('signed out', () => {
    it('/org/findings goes to login and remembers the target', async () => {
      renderApp('/org/findings')
      expect(await screen.findByTestId('login-page')).toBeInTheDocument()
      expect(pathname()).toBe('/login')
      expect(search()).toBe('?next=%2Forg%2Ffindings')
    })

    it('/settings/team goes to login and remembers the target', async () => {
      renderApp('/settings/team')
      expect(await screen.findByTestId('login-page')).toBeInTheDocument()
      expect(pathname()).toBe('/login')
      expect(search()).toBe('?next=%2Fsettings%2Fteam')
    })
  })

  describe('root, unknown paths, title', () => {
    it('/ signed in goes to the overview', async () => {
      signedIn()
      renderApp('/')
      expect(await screen.findByTestId('overview-page')).toBeInTheDocument()
      expect(pathname()).toBe('/overview')
    })

    it('/nope renders not-found', async () => {
      signedIn()
      renderApp('/nope')
      expect(await screen.findByTestId('not-found-page')).toBeInTheDocument()
    })

    it('/org/vendor-alerts while the org is loading shows the loading state, not the screen', async () => {
      signedIn({ orgLoading: true })
      renderApp('/org/vendor-alerts')
      expect(await screen.findByText('Loading...')).toBeInTheDocument()
      expect(screen.queryByTestId('vendor-alerts-tab')).not.toBeInTheDocument()
    })

    it('/settings/team while the org is loading shows the loading state, not the screen', async () => {
      signedIn({ orgLoading: true })
      renderApp('/settings/team')
      expect(await screen.findByText('Loading...')).toBeInTheDocument()
      expect(screen.queryByTestId('team-page')).not.toBeInTheDocument()
    })

    it('document title at /org/vendor-alerts', async () => {
      signedIn()
      renderApp('/org/vendor-alerts')
      await screen.findByTestId('vendor-alerts-tab')
      await waitFor(() => expect(document.title).toBe('Vendor Alerts · Hacker Tracker'))
    })
  })
})
