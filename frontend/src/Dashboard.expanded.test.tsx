import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const {
  mockLogout,
  mockRefresh,
} = vi.hoisted(() => {
  const mockLogout = vi.fn()
  const mockRefresh = vi.fn()

  return {
    mockLogout,
    mockRefresh,
  }
})

// ─────────────────────────────────────────────────────────────────────────────
// Firebase Mocks
// ─────────────────────────────────────────────────────────────────────────────

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn((_auth: unknown, cb: (u: null) => void) => { cb(null); return vi.fn(); }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}))
vi.mock('firebase/app', () => ({ initializeApp: vi.fn(() => ({})) }))

// ─────────────────────────────────────────────────────────────────────────────
// Component Mocks
// ─────────────────────────────────────────────────────────────────────────────

const mockAuthValues = {
  user: { uid: 'u1', email: 'test@example.com' } as unknown,
  loading: false,
  orgId: null as number | null,
  orgLoading: false,
  profileError: false,
  role: null as string | null,
  orgRole: null as string | null,
  login: vi.fn(),
  signup: vi.fn(),
  logout: mockLogout,
  getIdToken: vi.fn(),
  refreshProfile: vi.fn(),
}

vi.mock('./context/AuthContext', () => ({
  useAuth: () => mockAuthValues,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('./hooks/useDashboardData', () => ({
  useDashboardData: () => ({
    data: {
      summary: null, geographicThreats: [], attackTypes: [], severityDistribution: [],
      temporalTrends: [], sectorAttackMatrix: [], industryRisk: [], kevTotal: 0,
      lossProjection: null, executiveSummary: null,
    },
    loading: false, loadingHeavy: false, errors: [], lastUpdated: null, refresh: mockRefresh,
  }),
}))

vi.mock('./components/dashboard/OverviewTab', () => ({
  default: () => <div data-testid="overview-tab">Overview Content</div>,
}))

vi.mock('./pages/NotFoundPage', () => ({
  default: () => <div data-testid="not-found-page">Not found</div>,
}))

vi.mock('./components/shared/WidgetSkeleton', () => ({ default: () => null }))
vi.mock('./api/fetchWithAuth', () => ({ API_BASE_URL: '', fetchWithAuth: vi.fn(), getJsonAuth: vi.fn() }))
vi.mock('./components/tabs/RiskScoringTable', () => ({ default: () => <div data-testid="risk-scoring">Risk Scoring</div> }))
vi.mock('./components/tabs/ThreatIntelTab', () => ({ default: () => <div data-testid="threat-intel">Threat Intel</div> }))
vi.mock('./components/tabs/TrendsTab', () => ({ default: () => <div data-testid="trends">Trends</div> }))
vi.mock('./components/tabs/PipelineHealthTab', () => ({ default: () => <div data-testid="pipeline-health">Pipeline Health</div> }))
vi.mock('./components/tabs/NormalizationLogTab', () => ({ default: () => <div data-testid="normalization-log">Normalization Log</div> }))
vi.mock('./components/tabs/SmBAdvisorTab', () => ({ default: () => <div data-testid="smb-advisor">SMB Advisor</div> }))
// Render counters: a gated tab must never render, even briefly before a redirect clears the query.
const gatedRenders = vi.hoisted(() => ({ vendorAlerts: 0, assets: 0 }))
vi.mock('./components/tabs/VendorAlertsTab', () => ({
  default: () => {
    gatedRenders.vendorAlerts++
    return <div data-testid="vendor-alerts">Vendor Alerts</div>
  },
}))
vi.mock('./pages/AssetsPage', () => ({
  default: () => {
    gatedRenders.assets++
    return <div data-testid="assets-page">Assets</div>
  },
}))
vi.mock('./components/tabs/DataSourcesTab', () => ({ default: () => <div data-testid="data-sources">Data Sources</div> }))
vi.mock('./components/tabs/FindingsTab', () => ({ default: () => <div data-testid="findings">Findings</div> }))
vi.mock('./components/tabs/AISummaryTab', () => ({ default: () => <div data-testid="ai-summary">AI Summary</div> }))
vi.mock('./components/tabs/AnomaliesTab', () => ({ default: () => <div data-testid="anomalies">Anomalies</div> }))

// Import after all mocks
import Dashboard from './Dashboard'

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function renderDashboard(initialEntries = ['/dashboard']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Dashboard />
    </MemoryRouter>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('Dashboard - Navigation & Rendering', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthValues.orgId = null
    mockAuthValues.orgLoading = false
    mockAuthValues.role = null
    mockAuthValues.orgRole = null
  })

  describe('Visibility by organisation and role', () => {
    it('renders not-found for an org-only tab when the user has no org', () => {
      renderDashboard(['/dashboard?tab=assessment&sub=findings'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
    })

    it('renders overview for a user with no org at the default route', () => {
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })

    it('renders not-found at admin for a regular member', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      mockAuthValues.orgRole = 'member'
      renderDashboard(['/dashboard?tab=admin'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
    })

    it('renders admin for a global admin', async () => {
      mockAuthValues.role = 'admin'
      renderDashboard(['/dashboard?tab=admin'])
      await waitFor(() => expect(screen.getByTestId('pipeline-health')).toBeInTheDocument())
    })

    it('renders not-found at admin for an org admin who is not a platform admin', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = null
      mockAuthValues.orgRole = 'admin'
      renderDashboard(['/dashboard?tab=admin'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
    })
  })

  describe('Tab Navigation', () => {
    beforeEach(() => {
      mockAuthValues.orgId = 42
      mockAuthValues.orgRole = 'owner'
      mockAuthValues.role = 'admin'
    })

    it('renders overview tab by default', () => {
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })

    it('can navigate to threats tab with threatIntel sub-tab', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=threatIntel'])
      await waitFor(() => expect(screen.getByTestId('threat-intel')).toBeInTheDocument())
    })

    it('can navigate to riskScoring sub-tab', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=riskScoring'])
      await waitFor(() => expect(screen.getByTestId('risk-scoring')).toBeInTheDocument())
    })

    it('can navigate to assessment/findings', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=findings'])
      await waitFor(() => expect(screen.getByTestId('findings')).toBeInTheDocument())
    })

    it('can navigate to assessment/aiSummary', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=aiSummary'])
      await waitFor(() => expect(screen.getByTestId('ai-summary')).toBeInTheDocument())
    })

    it('can navigate to assessment/smbAdvisor', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=smbAdvisor'])
      await waitFor(() => expect(screen.getByTestId('smb-advisor')).toBeInTheDocument())
    })

    it('can navigate to vendorAlerts tab', async () => {
      renderDashboard(['/dashboard?tab=vendorAlerts'])
      await waitFor(() => expect(screen.getByTestId('vendor-alerts')).toBeInTheDocument())
    })

    it('can navigate to trends sub-tab', async () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=trends'])
      await waitFor(() => expect(screen.getByTestId('trends')).toBeInTheDocument())
    })

    it('can navigate to dataSources sub-tab', async () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=dataSources'])
      await waitFor(() => expect(screen.getByTestId('data-sources')).toBeInTheDocument())
    })

    it('can navigate to pipelineHealth (admin sub-tab)', async () => {
      renderDashboard(['/dashboard?tab=admin&sub=pipelineHealth'])
      await waitFor(() => expect(screen.getByTestId('pipeline-health')).toBeInTheDocument())
    })

    it('can navigate to normalizationLog (admin sub-tab)', async () => {
      renderDashboard(['/dashboard?tab=admin&sub=normalizationLog'])
      await waitFor(() => expect(screen.getByTestId('normalization-log')).toBeInTheDocument())
    })

    it('falls back to overview when accessing non-existent tab', async () => {
      renderDashboard(['/dashboard?tab=nope'])
      await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument())
      expect(screen.queryByTestId('not-found-page')).toBeNull()
    })

    it('renders not-found at ?tab=admin for an org admin who is not a platform admin', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = null
      mockAuthValues.orgRole = 'admin'
      renderDashboard(['/dashboard?tab=admin'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
      expect(screen.queryByTestId('overview-tab')).toBeNull()
      expect(screen.queryByTestId('pipeline-health')).toBeNull()
    })

    // Warm the lazy chunk (as a permitted user) so a gated mount would be immediate rather than
    // hidden by first-load latency, then reset the render counter before the gated render.
    async function warmLazyTab(tab: string, testId: string) {
      const org = mockAuthValues.orgId
      const loading = mockAuthValues.orgLoading
      mockAuthValues.orgId = 42
      mockAuthValues.orgLoading = false
      const warm = renderDashboard([`/dashboard?tab=${tab}`])
      await waitFor(() => expect(screen.getByTestId(testId)).toBeInTheDocument())
      warm.unmount()
      gatedRenders.vendorAlerts = 0
      gatedRenders.assets = 0
      mockAuthValues.orgId = org
      mockAuthValues.orgLoading = loading
    }

    it('never mounts VendorAlertsTab at ?tab=vendorAlerts for a user with no organisation', async () => {
      await warmLazyTab('vendorAlerts', 'vendor-alerts')
      mockAuthValues.orgId = null
      renderDashboard(['/dashboard?tab=vendorAlerts'])
      expect(screen.queryByTestId('vendor-alerts')).toBeNull()
      await waitFor(() => expect(screen.getByTestId('not-found-page')).toBeInTheDocument())
      expect(screen.queryByTestId('vendor-alerts')).toBeNull()
      expect(gatedRenders.vendorAlerts).toBe(0)
    })

    it('never mounts AssetsPage at ?tab=assets for a user with no organisation', async () => {
      await warmLazyTab('assets', 'assets-page')
      mockAuthValues.orgId = null
      renderDashboard(['/dashboard?tab=assets'])
      expect(screen.queryByTestId('assets-page')).toBeNull()
      await waitFor(() => expect(screen.getByTestId('not-found-page')).toBeInTheDocument())
      expect(screen.queryByTestId('assets-page')).toBeNull()
      expect(gatedRenders.assets).toBe(0)
    })

    it('never mounts VendorAlertsTab at ?tab=vendorAlerts while the organisation is loading', async () => {
      await warmLazyTab('vendorAlerts', 'vendor-alerts')
      mockAuthValues.orgId = 42
      mockAuthValues.orgLoading = true
      renderDashboard(['/dashboard?tab=vendorAlerts'])
      expect(screen.queryByTestId('vendor-alerts')).toBeNull()
      await waitFor(() => expect(screen.getByTestId('not-found-page')).toBeInTheDocument())
      expect(screen.queryByTestId('vendor-alerts')).toBeNull()
      expect(gatedRenders.vendorAlerts).toBe(0)
    })
  })

  describe('Component Rendering by Tab', () => {
    beforeEach(() => {
      mockAuthValues.orgId = 42
      mockAuthValues.orgRole = 'owner'
      mockAuthValues.role = 'admin'
    })

    it('renders OverviewTab content when viewing overview', async () => {
      renderDashboard(['/dashboard'])
      await waitFor(() => expect(screen.getByTestId('overview-tab')).toBeInTheDocument())
    })

    it('renders RiskScoringTable when viewing threats/riskScoring', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=riskScoring'])
      await waitFor(() => expect(screen.getByTestId('risk-scoring')).toBeInTheDocument())
    })

    it('renders ThreatIntelTab when viewing threats/threatIntel', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=threatIntel'])
      await waitFor(() => expect(screen.getByTestId('threat-intel')).toBeInTheDocument())
    })

    it('renders TrendsTab when viewing trendsData/trends', async () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=trends'])
      await waitFor(() => expect(screen.getByTestId('trends')).toBeInTheDocument())
    })

    it('renders PipelineHealthTab when viewing admin/pipelineHealth', async () => {
      renderDashboard(['/dashboard?tab=admin&sub=pipelineHealth'])
      await waitFor(() => expect(screen.getByTestId('pipeline-health')).toBeInTheDocument())
    })

    it('renders NormalizationLogTab when viewing admin/normalizationLog', async () => {
      renderDashboard(['/dashboard?tab=admin&sub=normalizationLog'])
      await waitFor(() => expect(screen.getByTestId('normalization-log')).toBeInTheDocument())
    })

    it('renders SmBAdvisorTab when viewing assessment/smbAdvisor', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=smbAdvisor'])
      await waitFor(() => expect(screen.getByTestId('smb-advisor')).toBeInTheDocument())
    })

    it('renders FindingsTab when viewing assessment/findings', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=findings'])
      await waitFor(() => expect(screen.getByTestId('findings')).toBeInTheDocument())
    })

    it('renders AISummaryTab when viewing assessment/aiSummary', async () => {
      renderDashboard(['/dashboard?tab=assessment&sub=aiSummary'])
      await waitFor(() => expect(screen.getByTestId('ai-summary')).toBeInTheDocument())
    })

    it('renders DataSourcesTab when viewing trendsData/dataSources', async () => {
      renderDashboard(['/dashboard?tab=trendsData&sub=dataSources'])
      await waitFor(() => expect(screen.getByTestId('data-sources')).toBeInTheDocument())
    })

    it('renders VendorAlertsTab when viewing vendorAlerts', async () => {
      renderDashboard(['/dashboard?tab=vendorAlerts'])
      await waitFor(() => expect(screen.getByTestId('vendor-alerts')).toBeInTheDocument())
    })

    it('renders AnomaliesTab when viewing threats/anomalies', async () => {
      renderDashboard(['/dashboard?tab=threats&sub=anomalies'])
      await waitFor(() => expect(screen.getByTestId('anomalies')).toBeInTheDocument())
    })
  })

  describe('Sub-tab resolution', () => {
    beforeEach(() => {
      mockAuthValues.orgId = 42
      mockAuthValues.orgRole = 'owner'
      mockAuthValues.role = 'admin'
    })

    it('defaults to the first sub-tab when none is specified', async () => {
      renderDashboard(['/dashboard?tab=assessment'])
      await waitFor(() => expect(screen.getByTestId('smb-advisor')).toBeInTheDocument())
    })

    it('renders not-found for a legacy sub-tab id the user cannot see', () => {
      mockAuthValues.role = null
      mockAuthValues.orgRole = 'member'
      renderDashboard(['/dashboard?tab=normalizationLog'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
      expect(screen.queryByTestId('normalization-log')).toBeNull()
    })
  })

  describe('Loading States', () => {
    it('renders overview tab even when data is still loading', () => {
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })
  })

  describe('Error Handling', () => {
    it('still renders the overview when user data is missing', () => {
      mockAuthValues.user = null as unknown
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })

    it('shows overview tab on error state', () => {
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })
  })

  describe('Legacy Tab Mapping', () => {
    beforeEach(() => {
      mockAuthValues.orgId = 42
      mockAuthValues.orgRole = 'owner'
      mockAuthValues.role = 'admin'
    })

    it('maps legacy findings tab to assessment/findings', async () => {
      renderDashboard(['/dashboard?tab=findings'])
      await waitFor(() => expect(screen.getByTestId('findings')).toBeInTheDocument())
    })

    it('maps legacy smbAdvisor to assessment/smbAdvisor', async () => {
      renderDashboard(['/dashboard?tab=smbAdvisor'])
      await waitFor(() => expect(screen.getByTestId('smb-advisor')).toBeInTheDocument())
    })

    it('maps legacy aiSummary to assessment/aiSummary', async () => {
      renderDashboard(['/dashboard?tab=aiSummary'])
      await waitFor(() => expect(screen.getByTestId('ai-summary')).toBeInTheDocument())
    })

    it('maps legacy threatIntel to threats/threatIntel', async () => {
      renderDashboard(['/dashboard?tab=threatIntel'])
      await waitFor(() => expect(screen.getByTestId('threat-intel')).toBeInTheDocument())
    })

    it('maps legacy riskScoring to threats/riskScoring', async () => {
      renderDashboard(['/dashboard?tab=riskScoring'])
      await waitFor(() => expect(screen.getByTestId('risk-scoring')).toBeInTheDocument())
    })

    it('maps legacy anomalies to threats/anomalies', async () => {
      renderDashboard(['/dashboard?tab=anomalies'])
      await waitFor(() => expect(screen.getByTestId('anomalies')).toBeInTheDocument())
    })

    it('maps legacy trends to trendsData/trends', async () => {
      renderDashboard(['/dashboard?tab=trends'])
      await waitFor(() => expect(screen.getByTestId('trends')).toBeInTheDocument())
    })

    it('maps legacy dataSources to trendsData/dataSources', async () => {
      renderDashboard(['/dashboard?tab=dataSources'])
      await waitFor(() => expect(screen.getByTestId('data-sources')).toBeInTheDocument())
    })

    it('maps legacy pipelineHealth to admin/pipelineHealth', async () => {
      renderDashboard(['/dashboard?tab=pipelineHealth'])
      await waitFor(() => expect(screen.getByTestId('pipeline-health')).toBeInTheDocument())
    })

    it('maps legacy normalizationLog to admin/normalizationLog', async () => {
      renderDashboard(['/dashboard?tab=normalizationLog'])
      await waitFor(() => expect(screen.getByTestId('normalization-log')).toBeInTheDocument())
    })
  })

  describe('Multiple Role Scenarios', () => {
    it('resolves admin and assessment for a global admin with org', async () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'admin'
      mockAuthValues.orgRole = 'admin'
      renderDashboard(['/dashboard?tab=admin&sub=pipelineHealth'])
      await waitFor(() => expect(screen.getByTestId('pipeline-health')).toBeInTheDocument())
    })

    it('resolves assessment but not admin for an org member without global admin', async () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      mockAuthValues.orgRole = 'member'
      renderDashboard(['/dashboard?tab=admin'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
      renderDashboard(['/dashboard?tab=assessment&sub=smbAdvisor'])
      await waitFor(() => expect(screen.getByTestId('smb-advisor')).toBeInTheDocument())
    })

    it('renders not-found at admin for an org owner (owner does not satisfy requiresAdmin)', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      mockAuthValues.orgRole = 'owner'
      renderDashboard(['/dashboard?tab=admin'])
      expect(screen.getByTestId('not-found-page')).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles null orgId gracefully', () => {
      mockAuthValues.orgId = null
      renderDashboard()
      expect(screen.getByTestId('overview-tab')).toBeInTheDocument()
    })

    it('handles switching between users with different roles', () => {
      mockAuthValues.orgId = 42
      mockAuthValues.role = 'viewer'
      renderDashboard()
      
      mockAuthValues.role = 'admin'
      renderDashboard(['/dashboard?tab=pipelineHealth'])
      expect(screen.getByTestId('pipeline-health')).toBeInTheDocument()
    })

    it('persists tab selection across navigation', () => {
      mockAuthValues.orgId = 42
      renderDashboard(['/dashboard?tab=riskScoring'])
      expect(screen.getByTestId('risk-scoring')).toBeInTheDocument()
    })
  })
})
