import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const { mockNavigate, mockAuthValues, mockFetchWithAuth, mockFetchIntake } = vi.hoisted(() => {
  const mockNavigate = vi.fn()
  const mockAuthValues = {
    user: { uid: 'u1', email: 'user@example.com' } as unknown,
    loading: false,
    orgId: 1 as number | null,
    orgLoading: false,
    profileError: false,
    role: null as string | null,
    orgRole: null as string | null,
    login: vi.fn(),
    signup: vi.fn(),
    logout: vi.fn(),
    getIdToken: vi.fn(),
    refreshProfile: vi.fn(),
  }
  const mockFetchWithAuth = vi.fn()
  const mockFetchIntake = vi.fn()

  return { mockNavigate, mockAuthValues, mockFetchWithAuth, mockFetchIntake }
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

vi.mock('../../api/fetchWithAuth', () => ({
  API_BASE_URL: '',
  fetchWithAuth: (...args: unknown[]) => mockFetchWithAuth(...args),
  getJsonAuth: vi.fn(),
}))

vi.mock('../../api/assessmentIntake', () => ({
  fetchAssessmentIntake: (...args: unknown[]) => mockFetchIntake(...args),
}))

// Import component AFTER mocks
import AssessmentIntakePage from '../AssessmentIntakePage'

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function renderPage() {
  return render(
    <MemoryRouter>
      <AssessmentIntakePage />
    </MemoryRouter>,
  )
}

function mockSuccessfulOrgFetch(orgData: Record<string, unknown> = {}) {
  mockFetchWithAuth.mockImplementation((url: string, options?: Record<string, unknown>) => {
    if (url.includes('/organizations/mine') && options?.method === 'GET') {
      return Promise.resolve({
        ok: true,
        json: async () => ({
          name: 'Acme Corp',
          industry_label: 'Technology',
          primary_state: 'CA',
          employee_range: '51-200',
          security_controls: {},
          compliance_frameworks: [],
          data_types: [],
          cloud_providers: [],
          ...orgData,
        }),
      })
    }
    if (url.includes('/organizations/mine') && options?.method === 'PATCH') {
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      })
    }
    return Promise.resolve({
      ok: true,
      json: async () => ({}),
    })
  })
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('AssessmentIntakePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthValues.user = { uid: 'u1', email: 'user@example.com' } as unknown
    mockAuthValues.orgId = 1
    mockFetchIntake.mockResolvedValue({
      current_tier: 'basic',
      tiers: [
        {
          tier: 'basic',
          label: 'Basic',
          description: 'Basic tier',
          requirements: [],
          all_met: true,
          unlocks: [],
        },
      ],
      next_tier: 'enhanced',
      next_tier_progress: 50,
      fields_to_advance: [],
    })
    mockSuccessfulOrgFetch()
  })

  it('renders without crashing on step 1', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText(/Set Up Your Organization|company|Company/i)).toBeInTheDocument()
    })
  })

  it('shows step indicator', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('Step 1 of 5')).toBeInTheDocument()
    })
  })

  it('renders company basics form fields', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByLabelText(/Company Name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/Industry/i)).toBeInTheDocument()
    })
  })

  it('requires all step 1 fields before advancing', () => {
    renderPage()
    const nextBtn = screen.getByRole('button', { name: /Next/i })

    expect(nextBtn).toBeDisabled()

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })

    expect(nextBtn).not.toBeDisabled()
  })

  it('advances to step 2 with valid step 1 data', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => {
      expect(screen.getByText('Step 2 of 5')).toBeInTheDocument()
    })
  })

  it('shows previous button on step 2+', async () => {
    renderPage()

    expect(screen.queryByRole('button', { name: /Previous/i })).not.toBeInTheDocument()

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Previous/i })).toBeInTheDocument()
    })
  })

  it('navigates back to previous step', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => {
      expect(screen.getByText('Step 2 of 5')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Previous/i }))

    await waitFor(() => {
      expect(screen.getByText('Step 1 of 5')).toBeInTheDocument()
    })
  })

  it('shows Financial & Compliance section on step 2', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => {
      expect(screen.getByText(/Annual Revenue|Revenue|financial/i)).toBeInTheDocument()
    })
  })

  it('shows Security Controls on step 3', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 2 of 5')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => {
      expect(screen.getByText('Step 3 of 5')).toBeInTheDocument()
    })
  })

  it('requires security control selection on step 3', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 2 of 5')).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 3 of 5')).toBeInTheDocument())

    const nextBtn = screen.getByRole('button', { name: /Next/i })
    expect(nextBtn).toBeDisabled()
  })

  it('loads existing organization data', async () => {
    mockSuccessfulOrgFetch({
      name: 'Existing Corp',
      industry_label: 'Healthcare',
    })

    renderPage()

    await waitFor(() => {
      const nameInput = screen.getByLabelText(/Company Name/i) as HTMLInputElement
      expect(nameInput.value).toBe('Existing Corp')
    })
  })

  it('saves form data when advancing steps', async () => {
    renderPage()

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => {
      expect(mockFetchWithAuth).toHaveBeenCalledWith(
        expect.stringContaining('/organizations/mine'),
        expect.objectContaining({ method: 'PATCH' }),
      )
    })
  })

  it('retains form data when navigating back', async () => {
    renderPage()

    const companyName = 'Test Corp'
    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: companyName },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => {
      expect(screen.getByText('Step 2 of 5')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Previous/i }))

    await waitFor(() => {
      const nameInput = screen.getByLabelText(/Company Name/i) as HTMLInputElement
      expect(nameInput.value).toBe(companyName)
    })
  })

  it('redirects to onboarding when user has no org', () => {
    mockAuthValues.orgId = null

    renderPage()

    expect(mockNavigate).toHaveBeenCalledWith('/onboarding')
  })

  it('navigates to dashboard on form submission', async () => {
    renderPage()

    // Fill and submit through all steps
    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 2 of 5')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 3 of 5')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 4 of 5')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 5 of 5')).toBeInTheDocument())

    const submitBtn = screen.getByRole('button', { name: /Submit|Finish/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/dashboard')
    })
  })

  it('shows error message on submission failure', async () => {
    mockFetchWithAuth.mockImplementation((url: string, options?: Record<string, unknown>) => {
      if (url.includes('/organizations/mine') && options?.method === 'PATCH') {
        return Promise.resolve({
          ok: false,
          json: async () => ({ detail: 'Validation failed' }),
        })
      }
      return Promise.resolve({
        ok: true,
        json: async () => ({}),
      })
    })

    renderPage()

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.change(screen.getByLabelText(/Industry/i), {
      target: { value: 'Technology' },
    })
    fireEvent.change(screen.getByLabelText(/Primary State/i), {
      target: { value: 'CA' },
    })
    fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
      target: { value: '51-200' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 2 of 5')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 3 of 5')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 4 of 5')).toBeInTheDocument())
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => expect(screen.getByText('Step 5 of 5')).toBeInTheDocument())

    const submitBtn = screen.getByRole('button', { name: /Submit|Finish/i })
    fireEvent.click(submitBtn)

    await waitFor(() => {
      expect(screen.getByText(/Validation failed/i)).toBeInTheDocument()
    })
  })
})
