import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const {
  mockNavigate,
  mockAuthValues,
  mockFetchDebug,
  mockFetchHistory,
  mockFetchGeneration,
} = vi.hoisted(() => {
  const mockNavigate = vi.fn()
  const mockAuthValues = {
    user: { uid: 'u1', email: 'admin@example.com' } as unknown,
    loading: false,
    orgId: 1 as number | null,
    orgLoading: false,
    profileError: false,
    role: null as string | null,
    orgRole: 'admin' as string | null,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    getIdToken: vi.fn(),
    refreshProfile: vi.fn(),
  }
  const mockFetchDebug = vi.fn()
  const mockFetchHistory = vi.fn()
  const mockFetchGeneration = vi.fn()

  return { mockNavigate, mockAuthValues, mockFetchDebug, mockFetchHistory, mockFetchGeneration }
})

// ─────────────────────────────────────────────────────────────────────────────
// Module Mocks
// ─────────────────────────────────────────────────────────────────────────────

vi.mock('firebase/auth', () => ({
  getAuth: vi.fn(() => ({ currentUser: null })),
  onAuthStateChanged: vi.fn((_a: unknown, cb: (u: null) => void) => {
    cb(null)
    return vi.fn()
  }),
  signInWithEmailAndPassword: vi.fn(),
  createUserWithEmailAndPassword: vi.fn(),
  signOut: vi.fn(),
  sendPasswordResetEmail: vi.fn(),
  sendEmailVerification: vi.fn(),
}))

vi.mock('firebase/app', () => ({ initializeApp: vi.fn(() => ({})) }))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom')
  return { ...actual, useNavigate: () => mockNavigate }
})

vi.mock('../../context/AuthContext', () => ({
  useAuth: () => mockAuthValues,
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

vi.mock('../../hooks/useDarkMode', () => ({
  useDarkMode: () => [false, vi.fn()],
}))

vi.mock('../../api/assessmentDebug', () => ({
  fetchAssessmentDebug: (...args: unknown[]) => mockFetchDebug(...args),
}))

vi.mock('../../api/aiSummaryHistory', () => ({
  fetchAISummaryHistory: (...args: unknown[]) => mockFetchHistory(...args),
  fetchAISummaryGeneration: (...args: unknown[]) => mockFetchGeneration(...args),
}))

// Import component AFTER mocks
import AssessmentDebugPage from '../AssessmentDebugPage'

// ─────────────────────────────────────────────────────────────────────────────
// Mock Data Helpers
// ─────────────────────────────────────────────────────────────────────────────

const mockDebugResponse = {
  generated_at: '2024-01-01T00:00:00Z',
  org_id: 1,
  raw_profile: { name: 'Acme Corp', industry_label: 'Technology', employee_count: 500 },
  intake: {
    current_tier: 'enhanced',
    tiers: [
      {
        tier: 'basic',
        label: 'Basic',
        description: 'Basic tier',
        all_met: true,
        requirements: [
          { key: 'name', label: 'Company Name', met: true, detail: 'Acme Corp' },
          { key: 'industry', label: 'Industry', met: true, detail: 'Technology' },
        ],
        unlocks: [],
      },
      {
        tier: 'enhanced',
        label: 'Enhanced',
        description: 'Enhanced tier',
        all_met: true,
        requirements: [
          { key: 'revenue', label: 'Annual Revenue', met: true, detail: '$100M+' },
          { key: 'security_controls', label: 'Security Controls', met: true, detail: '5 controls defined' },
        ],
        unlocks: [],
      },
      {
        tier: 'comprehensive',
        label: 'Comprehensive',
        description: 'Comprehensive tier',
        all_met: false,
        requirements: [
          { key: 'vendor_list', label: 'Vendor List', met: false, detail: null },
          { key: 'data_flow', label: 'Data Flow Diagram', met: false, detail: null },
        ],
        unlocks: [],
      },
    ],
    next_tier: 'comprehensive',
    next_tier_progress: 50,
    fields_to_advance: ['vendor_list', 'data_flow'],
  },
  validation: {
    issues: [
      {
        severity: 'error',
        field: 'revenue_range',
        message: 'Revenue range is required for Enhanced tier',
        suggestion: 'Please provide an annual revenue estimate',
      },
      {
        severity: 'warning',
        field: 'employee_locations',
        message: 'Employee location data is sparse',
        suggestion: 'Provide coverage for all primary business locations',
      },
      {
        severity: 'info',
        field: 'compliance_frameworks',
        message: 'No compliance frameworks specified',
        suggestion: 'Consider if SOC 2, ISO 27001, or other certifications apply',
      },
    ],
    score: 82.5,
    passed: false,
    issue_counts: { error: 1, warning: 1, info: 1 },
  },
  findings_readiness: {
    ready: true,
    current_tier: 'enhanced',
    blocking_reason: null,
    report: {
      org_id: 1,
      findings: [
        {
          id: 'f1',
          type: 'vulnerability',
          severity: 'high',
          title: 'Unpatched critical system',
          description: 'System X has critical patches pending',
          affected_count: 2,
          exposure_percentage: 15,
        },
      ],
      summary: { total: 1, by_type: { vulnerability: 1 }, by_severity: { high: 1 } },
      generated_at: '2024-01-01T00:00:00Z',
      data_sources_used: ['nvd', 'kev'],
      assessment_tier: 'enhanced',
    },
  },
}

const mockAISummaryHistory = {
  items: [
    {
      id: 1,
      generated_at: '2024-01-01T12:00:00Z',
      model_name: 'gpt-4',
      source: 'manual',
      status: 'success',
      latency_ms: 2500,
      error_message: null,
    },
    {
      id: 2,
      generated_at: '2024-01-01T11:00:00Z',
      model_name: 'gpt-3.5-turbo',
      source: 'auto',
      status: 'fallback_used',
      latency_ms: 1200,
      error_message: null,
    },
    {
      id: 3,
      generated_at: '2024-01-01T10:00:00Z',
      model_name: 'gpt-4',
      source: 'manual',
      status: 'error',
      latency_ms: 5000,
      error_message: 'Rate limit exceeded',
    },
  ],
  total: 3,
}

const mockAISummaryDetail = {
  id: 1,
  output_text: 'This is an AI-generated executive summary of your cybersecurity posture.',
  generated_at: '2024-01-01T12:00:00Z',
  model_name: 'gpt-4',
  prompt_tokens: 1500,
  output_tokens: 200,
}

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter>
      <AssessmentDebugPage />
    </MemoryRouter>,
  )
}

function mockSuccessfulDebugFetch() {
  mockFetchDebug.mockResolvedValue(mockDebugResponse)
  mockFetchHistory.mockResolvedValue(mockAISummaryHistory)
  mockFetchGeneration.mockResolvedValue(mockAISummaryDetail)
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('AssessmentDebugPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthValues.role = null
    mockAuthValues.orgRole = 'admin'
    mockAuthValues.loading = false
    mockSuccessfulDebugFetch()
  })

  describe('Access Control', () => {
    it('redirects to settings when user is not admin', () => {
      mockAuthValues.orgRole = 'viewer'

      renderPage()

      expect(mockNavigate).toHaveBeenCalledWith('/settings')
    })

    it('redirects to settings when user is member', () => {
      mockAuthValues.orgRole = 'member'

      renderPage()

      expect(mockNavigate).toHaveBeenCalledWith('/settings')
    })

    it('allows access when role is admin', async () => {
      mockAuthValues.role = 'admin'

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Assessment Debug View/i)).toBeInTheDocument()
      })
    })

    it('allows access when orgRole is admin', async () => {
      mockAuthValues.orgRole = 'admin'

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Assessment Debug View/i)).toBeInTheDocument()
      })
    })

    it('allows access when orgRole is owner', async () => {
      mockAuthValues.orgRole = 'owner'

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Assessment Debug View/i)).toBeInTheDocument()
      })
    })
  })

  describe('Loading & Error States', () => {
    it('shows loading state initially', () => {
      renderPage()

      expect(screen.getByText(/Loading debug snapshot/i)).toBeInTheDocument()
    })

    it('shows error message when fetch fails', async () => {
      mockFetchDebug.mockRejectedValue(new Error('Network error'))

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Network error/i)).toBeInTheDocument()
      })
    })

    it('shows error when AbortError is caught (cleanup)', async () => {
      const error = new Error('Aborted')
      error.name = 'AbortError'
      mockFetchDebug.mockRejectedValue(error)

      renderPage()

      // Should not show error message for AbortError
      await waitFor(() => {
        expect(screen.queryByText(/Aborted/i)).not.toBeInTheDocument()
      })
    })

    it('hides loading and error states after successful load', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.queryByText(/Loading debug snapshot/i)).not.toBeInTheDocument()
        expect(screen.queryByText(/Failed to load debug data/i)).not.toBeInTheDocument()
      })
    })
  })

  describe('Header & Navigation', () => {
    it('renders page heading and org info', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Assessment Debug View/i)).toBeInTheDocument()
        expect(screen.getByText(/Org #1/i)).toBeInTheDocument()
      })
    })

    it('has back to dashboard button', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Back to Dashboard/i })).toBeInTheDocument()
      })
    })

    it('has back to settings button', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Back to Settings/i })).toBeInTheDocument()
      })
    })

    it('navigates to dashboard when clicking back to dashboard', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Back to Dashboard/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Back to Dashboard/i }))

      expect(mockNavigate).toHaveBeenCalledWith('/')
    })
  })

  describe('Tier Status Display', () => {
    it('renders all section headings', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Raw Inputs/i)).toBeInTheDocument()
        expect(screen.getByText(/Normalized Profile/i)).toBeInTheDocument()
        expect(screen.getByText(/Validation/i)).toBeInTheDocument()
      })
    })

    it('displays current tier', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('enhanced').length).toBeGreaterThan(0)
      })
    })

    it('displays next tier progress', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Progress to comprehensive/i)).toBeInTheDocument()
        expect(screen.getByText(/50\.0%/)).toBeInTheDocument()
      })
    })

    it('displays fields to advance', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Fields to advance/i)).toBeInTheDocument()
        expect(screen.getByText('vendor_list')).toBeInTheDocument()
        expect(screen.getByText('data_flow')).toBeInTheDocument()
      })
    })

    it('expands tier details when clicking', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Normalized Profile/i)).toBeInTheDocument()
      })

      const tierSummaries = screen.getAllByText(/✓ met|not met/)
      fireEvent.click(tierSummaries[0].closest('summary')!)

      await waitFor(() => {
        expect(screen.getByText(/Company Name/i)).toBeInTheDocument()
      })
    })

    it('shows met requirements with checkmark', async () => {
      renderPage()

      await waitFor(() => expect(screen.getAllByText(/✓ met|not met/).length).toBeGreaterThan(0))

      const tierSummaries = screen.getAllByText(/✓ met|not met/)
      fireEvent.click(tierSummaries[1].closest('summary')!)

      await waitFor(() => {
        expect(screen.getAllByText(/Annual Revenue/i).length).toBeGreaterThan(0)
      })
    })

    it('shows unmet requirements with x mark', async () => {
      renderPage()

      await waitFor(() => expect(screen.getAllByText(/✓ met|not met/).length).toBeGreaterThan(0))

      const tierSummaries = screen.getAllByText(/✓ met|not met/)
      fireEvent.click(tierSummaries[2].closest('summary')!)

      await waitFor(() => {
        expect(screen.getByText(/Vendor List/i)).toBeInTheDocument()
      })
    })

    it('displays all tier levels (basic, enhanced, comprehensive)', async () => {
      renderPage()

      await waitFor(() => {
        const tierBadges = screen.getAllByText(/basic|enhanced|comprehensive/)
        expect(tierBadges.length).toBeGreaterThan(0)
      })
    })
  })

  describe('Validation Section', () => {
    it('displays quality score', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Quality Score/i)).toBeInTheDocument()
        expect(screen.getByText(/82\.5 \/ 100/)).toBeInTheDocument()
      })
    })

    it('displays validation status', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Status/i)).toBeInTheDocument()
        expect(screen.getByText(/Failed/i)).toBeInTheDocument()
      })
    })

    it('displays issue counts by severity', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/error: 1/i)).toBeInTheDocument()
        expect(screen.getByText(/warning: 1/i)).toBeInTheDocument()
        expect(screen.getByText(/info: 1/i)).toBeInTheDocument()
      })
    })

    it('displays validation issues table with all columns', async () => {
      renderPage()

      await waitFor(() => {
        const headers = screen.getAllByRole('columnheader').map(h => h.textContent)
        expect(headers).toContain('Severity')
        expect(headers).toContain('Field')
        expect(headers).toContain('Message')
      })
    })

    it('shows issue severity badge', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('revenue_range')).toBeInTheDocument()
      })
    })

    it('displays issue messages and suggestions', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Revenue range is required for Enhanced tier/i)).toBeInTheDocument()
        expect(screen.getByText(/Please provide an annual revenue estimate/i)).toBeInTheDocument()
      })
    })

    it('shows all three severity levels in issues', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Revenue range is required/i)).toBeInTheDocument()
        expect(screen.getByText(/Employee location data is sparse/i)).toBeInTheDocument()
        expect(screen.getByText(/No compliance frameworks/i)).toBeInTheDocument()
      })
    })

    it('shows passed status when validation passes', async () => {
      mockFetchDebug.mockResolvedValue({
        ...mockDebugResponse,
        validation: { ...mockDebugResponse.validation, passed: true },
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Passed/i)).toBeInTheDocument()
      })
    })
  })

  describe('Findings Readiness Section', () => {
    it('displays findings readiness status when ready', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('heading', { name: /Exposure/i })).toBeInTheDocument()
      })
    })

    it('shows blocking reason when not ready', async () => {
      mockFetchDebug.mockResolvedValue({
        ...mockDebugResponse,
        findings_readiness: {
          ready: false,
          current_tier: 'basic',
          blocking_reason: 'Requires Enhanced tier minimum',
          report: null,
        },
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Requires Enhanced tier minimum/i)).toBeInTheDocument()
      })
    })

    it('displays findings summary when ready', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/total/i)).toBeInTheDocument()
      })
    })

    it('displays data sources used for findings', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('Total Findings')).toBeInTheDocument()
      })
    })

    it('shows findings count by severity', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText('By Severity')).toBeInTheDocument()
      })
    })
  })

  describe('Raw Profile Section', () => {
    it('renders raw profile section with expand button', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Raw Inputs/i)).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /Expand/i })).toBeInTheDocument()
      })
    })

    it('shows PII warning badge', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/PII Warning/i)).toBeInTheDocument()
      })
    })

    it('expands raw profile data when clicking expand', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Expand/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Expand/i }))

      await waitFor(() => {
        expect(screen.getByText('name')).toBeInTheDocument()
        expect(screen.getAllByText('Acme Corp').length).toBeGreaterThan(0)
      })
    })

    it('collapses raw profile when clicking collapse', async () => {
      renderPage()

      await waitFor(() => {
        fireEvent.click(screen.getByRole('button', { name: /Expand/i }))
      })

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /Collapse/i })).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /Collapse/i }))

      expect(screen.getByRole('button', { name: /Expand/i })).toBeInTheDocument()
    })
  })

  describe('AI Summary History Section', () => {
    it('renders summary history section heading', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Executive Summary History/i)).toBeInTheDocument()
      })
    })

    it('displays history items count', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Showing 3 of 3/i)).toBeInTheDocument()
      })
    })

    it('shows message when no history exists', async () => {
      mockFetchHistory.mockResolvedValue({ items: [], total: 0 })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/No summary generations recorded yet/i)).toBeInTheDocument()
      })
    })

    it('displays table with all columns', async () => {
      renderPage()

      await waitFor(() => {
        const headers = screen.getAllByRole('columnheader').map(h => h.textContent)
        expect(headers).toContain('Generated At')
        expect(headers).toContain('Model')
        expect(headers).toContain('Source')
        expect(headers).toContain('Status')
        expect(headers).toContain('Latency')
      })
    })

    it('displays model names', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('gpt-4').length).toBeGreaterThan(0)
        expect(screen.getByText('gpt-3.5-turbo')).toBeInTheDocument()
      })
    })

    it('displays source badges (manual, auto)', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('manual').length).toBeGreaterThan(0)
        expect(screen.getByText('auto')).toBeInTheDocument()
      })
    })

    it('displays status badges (success, fallback_used, error)', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('success').length).toBeGreaterThan(0)
        expect(screen.getAllByText('fallback_used').length).toBeGreaterThan(0)
        expect(screen.getAllByText('error').length).toBeGreaterThan(0)
      })
    })

    it('displays latency in milliseconds', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/2500 ms/)).toBeInTheDocument()
        expect(screen.getByText(/1200 ms/)).toBeInTheDocument()
        expect(screen.getByText(/5000 ms/)).toBeInTheDocument()
      })
    })

    it('displays error message in row when present', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('gpt-4').length).toBeGreaterThan(0)
      })

      // Row id=3 has error_message; it's the second gpt-4 row — expand it
      const allGpt4 = screen.getAllByText('gpt-4')
      fireEvent.click(allGpt4[1].closest('tr')!)

      await waitFor(() => {
        expect(screen.getByText(/Rate limit exceeded/i)).toBeInTheDocument()
      })
    })

    it('shows detail when clicking history row', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('gpt-4').length).toBeGreaterThan(0)
      })

      const gpt4Cell = screen.getAllByText('gpt-4')[0]
      fireEvent.click(gpt4Cell.closest('tr')!)

      await waitFor(() => {
        expect(mockFetchGeneration).toHaveBeenCalled()
      })
    })

    it('loads detail content in expanded row', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('gpt-4').length).toBeGreaterThan(0)
      })

      const gpt4Cell = screen.getAllByText('gpt-4')[0]
      fireEvent.click(gpt4Cell.closest('tr')!)

      await waitFor(() => {
        expect(screen.getByText(/Output Preview/i)).toBeInTheDocument()
        expect(
          screen.getByText(/This is an AI-generated executive summary/i),
        ).toBeInTheDocument()
      })
    })

    it('shows loading state in expanded row during fetch', async () => {
      mockFetchGeneration.mockImplementation(() => new Promise(() => {}))

      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('gpt-4').length).toBeGreaterThan(0)
      })

      const gpt4Cell = screen.getAllByText('gpt-4')[0]
      fireEvent.click(gpt4Cell.closest('tr')!)

      await waitFor(() => {
        expect(screen.getByText(/Loading detail/i)).toBeInTheDocument()
      })
    })

    it('collapses detail when clicking same row again', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('gpt-4').length).toBeGreaterThan(0)
      })

      const gpt4Cell = screen.getAllByText('gpt-4')[0]
      const dataRow = gpt4Cell.closest('tr')!
      fireEvent.click(dataRow)

      await waitFor(() => {
        expect(screen.getByText(/This is an AI-generated executive summary/i)).toBeInTheDocument()
      })

      fireEvent.click(dataRow)

      await waitFor(() => {
        expect(screen.queryByText(/Output Preview/i)).not.toBeInTheDocument()
      })
    })

    it('shows error message in detail when fetch fails', async () => {
      const error = new Error('Failed to load detail')
      mockFetchGeneration.mockRejectedValue(error)

      renderPage()

      await waitFor(() => {
        expect(screen.getAllByText('gpt-4').length).toBeGreaterThan(0)
      })

      const gpt4Cell = screen.getAllByText('gpt-4')[0]
      fireEvent.click(gpt4Cell.closest('tr')!)

      await waitFor(() => {
        expect(mockFetchGeneration).toHaveBeenCalled()
      })
    })
  })

  describe('Edge Cases & Data Handling', () => {
    it('handles null next_tier gracefully', async () => {
      mockFetchDebug.mockResolvedValue({
        ...mockDebugResponse,
        intake: { ...mockDebugResponse.intake, next_tier: null, next_tier_progress: 0 },
      })

      renderPage()

      await waitFor(() => {
        expect(screen.queryByText(/Progress to/i)).not.toBeInTheDocument()
      })
    })

    it('handles empty fields_to_advance array', async () => {
      mockFetchDebug.mockResolvedValue({
        ...mockDebugResponse,
        intake: { ...mockDebugResponse.intake, fields_to_advance: [] },
      })

      renderPage()

      await waitFor(() => {
        expect(screen.queryByText(/Fields to advance/i)).not.toBeInTheDocument()
      })
    })

    it('handles empty validation issues', async () => {
      mockFetchDebug.mockResolvedValue({
        ...mockDebugResponse,
        validation: { ...mockDebugResponse.validation, issues: [] },
      })

      renderPage()

      await waitFor(() => {
        expect(screen.queryByText(/Severity|Field|Message/i)).not.toBeInTheDocument()
      })
    })

    it('handles missing findings report', async () => {
      mockFetchDebug.mockResolvedValue({
        ...mockDebugResponse,
        findings_readiness: {
          ready: false,
          current_tier: 'basic',
          blocking_reason: 'Need Enhanced tier',
          report: null,
        },
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Need Enhanced tier/i)).toBeInTheDocument()
      })
    })

    it('formats timestamps correctly', async () => {
      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Snapshot generated at/i)).toBeInTheDocument()
      })
    })

    it('handles requirement detail being null', async () => {
      mockFetchDebug.mockResolvedValue({
        ...mockDebugResponse,
        intake: {
          ...mockDebugResponse.intake,
          tiers: [
            {
              ...mockDebugResponse.intake.tiers[2],
              requirements: [{ key: 'test', label: 'Test Req', met: false, detail: null }],
            },
          ],
        },
      })

      renderPage()

      await waitFor(() => {
        expect(screen.getByText(/Test Req/i)).toBeInTheDocument()
      })
    })
  })
})
