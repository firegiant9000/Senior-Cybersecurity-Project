import { render, screen, waitFor, fireEvent, act } from '@testing-library/react'
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// ─────────────────────────────────────────────────────────────────────────────
// Hoisted Mocks
// ─────────────────────────────────────────────────────────────────────────────

const { mockNavigate, mockAuthValues, authStore, mockFetchWithAuth, mockFetchIntake, mockCreateVendor } = vi.hoisted(() => {
  const mockNavigate = vi.fn()
  // Lets a test change mockAuthValues mid-render (e.g. orgId becoming set once
  // the wizard has created the organisation) and have the page re-render.
  const authStore = { version: 0, listeners: new Set<() => void>() }
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
  const mockCreateVendor = vi.fn()

  return { mockNavigate, mockAuthValues, authStore, mockFetchWithAuth, mockFetchIntake, mockCreateVendor }
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

vi.mock('../../context/AuthContext', async () => {
  const { useSyncExternalStore } = await import('react')
  return {
    useAuth: () => {
      useSyncExternalStore(
        (cb) => {
          authStore.listeners.add(cb)
          return () => authStore.listeners.delete(cb)
        },
        () => authStore.version,
      )
      return mockAuthValues
    },
    AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  }
})

vi.mock('../../api/fetchWithAuth', () => ({
  API_BASE_URL: '',
  fetchWithAuth: (...args: unknown[]) => mockFetchWithAuth(...args),
  getJsonAuth: vi.fn(),
}))

vi.mock('../../api/assessmentIntake', () => ({
  fetchAssessmentIntake: (...args: unknown[]) => mockFetchIntake(...args),
  // Added because e52ab31 (live tier-progress indicator) introduced this
  // export; without stubbing it, AssessmentIntakePage's useIntakePreview hook
  // throws a "No export defined" error during test runs.
  previewAssessmentIntake: vi.fn().mockResolvedValue({
    current_tier: 'basic',
    tiers: [],
    next_tier: null,
    next_tier_progress: 0,
    fields_to_advance: [],
  }),
  // Imported by AssessmentIntakePage; without these stubs vitest logs a
  // "No export defined" warning whenever the wizard reaches them.
  completeIntake: vi.fn().mockResolvedValue(undefined),
  skipIntakeStep: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('../../api/vendors', () => ({
  createVendor: (...args: unknown[]) => mockCreateVendor(...args),
}))

// Import component AFTER mocks
import AssessmentIntakePage from '../AssessmentIntakePage'
import { completeIntake } from '../../api/assessmentIntake'

// ─────────────────────────────────────────────────────────────────────────────
// Helper Functions
// ─────────────────────────────────────────────────────────────────────────────

function LocationProbe() {
  return <div data-testid="location">{useLocation().pathname}</div>
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/onboarding']}>
      <Routes>
        <Route path="/onboarding" element={<AssessmentIntakePage />} />
        <Route path="/settings/organisation" element={<div>Organisation settings</div>} />
      </Routes>
      <LocationProbe />
    </MemoryRouter>,
  )
}

// Changes the auth context the way a real auth refresh would and re-renders
// subscribers. refreshProfile uses it to set orgId after the wizard creates
// the organisation; entry-capture tests use it to finish loading.
async function setAuth(patch: { orgLoading?: boolean; orgId?: number | null }) {
  await act(async () => {
    Object.assign(mockAuthValues, patch)
    authStore.version += 1
    authStore.listeners.forEach((l) => l())
  })
}

// Matches /organizations/{orgId} but not sub-resource URLs like /organizations/1/domains
const isMainOrgUrl = (url: string) => /\/organizations\/(\d+|mine)$/.test(url)

function mockSuccessfulOrgFetch() {
  mockFetchWithAuth.mockImplementation((url: string, options?: Record<string, unknown>) => {
    if (isMainOrgUrl(url) && options?.method === 'PUT') {
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

// Fill step 1 with values that match real option lists. Tests previously used
// 'Technology' (not in INDUSTRY_OPTIONS) so the controlled <select> rejected the
// value, keeping form.industry_label empty and Next disabled.
function fillStep1() {
  fireEvent.change(screen.getByLabelText(/Company Name/i), {
    target: { value: 'Test Corp' },
  })
  fireEvent.change(screen.getByLabelText(/Industry/i), {
    target: { value: 'Tech & Software' },
  })
  fireEvent.change(screen.getByLabelText(/Primary State/i), {
    target: { value: 'CA' },
  })
  fireEvent.change(screen.getByLabelText(/Number of Employees/i), {
    target: { value: '51-200' },
  })
}

// Step heading helpers — the page never renders "Step N of 5" text, so tests
// must assert on the FormSection h3 (or h1 review heading) for the active step.
const stepHeading = {
  1: { level: 3, name: /^Company Information$/ },
  2: { level: 3, name: /^Financial & Compliance/ },
  3: { level: 3, name: /^Security Controls$/ },
  4: { level: 3, name: /^Technology & Infrastructure$/ },
  5: { level: 3, name: /^Review Your Assessment Intake$/ },
} as const

function expectOnStep(step: 1 | 2 | 3 | 4 | 5) {
  return waitFor(() => {
    expect(
      screen.getByRole('heading', stepHeading[step]),
    ).toBeInTheDocument()
  })
}

// Click the first security control's "Yes" button so step 3 becomes valid.
function selectFirstSecurityControl() {
  const yesButtons = screen.getAllByRole('button', { name: /^Yes$/i })
  fireEvent.click(yesButtons[0])
}

// ─────────────────────────────────────────────────────────────────────────────
// Tests
// ─────────────────────────────────────────────────────────────────────────────

describe('AssessmentIntakePage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockAuthValues.user = { uid: 'u1', email: 'user@example.com' } as unknown
    // The wizard is first-run only: it is entered with no organisation, creates
    // one on step 1 and sees orgId become set from then on.
    mockAuthValues.orgId = null
    mockAuthValues.orgLoading = false
    mockAuthValues.refreshProfile = vi.fn(() => setAuth({ orgId: 7 }))
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
      expect(
        screen.getByRole('heading', { level: 1, name: 'Set up your organisation' }),
      ).toBeInTheDocument()
    })
  })

  it('shows step indicator', async () => {
    renderPage()
    await expectOnStep(1)
  })

  it('renders company basics form fields', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByLabelText(/Company Name/i)).toBeInTheDocument()
      expect(screen.getByLabelText(/Industry/i)).toBeInTheDocument()
    })
  })

  it('requires all step 1 fields before advancing', async () => {
    renderPage()

    // Wait for org load to settle so it doesn't overwrite our values mid-test.
    await expectOnStep(1)

    const nextBtn = screen.getByRole('button', { name: /Next/i })
    expect(nextBtn).toBeDisabled()

    fillStep1()

    expect(nextBtn).not.toBeDisabled()
  })

  it('advances to step 2 with valid step 1 data', async () => {
    renderPage()
    await expectOnStep(1)

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await expectOnStep(2)
  })

  it('shows previous button on step 2+', async () => {
    renderPage()
    await expectOnStep(1)

    expect(screen.getByRole('button', { name: /Previous/i })).toBeDisabled()

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Previous/i })).not.toBeDisabled()
    })
  })

  it('navigates back to previous step', async () => {
    renderPage()
    await expectOnStep(1)

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(2)

    fireEvent.click(screen.getByRole('button', { name: /Previous/i }))
    await expectOnStep(1)
  })

  it('shows Financial & Compliance section on step 2', async () => {
    renderPage()
    await expectOnStep(1)

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))

    await expectOnStep(2)
    expect(screen.getByText(/Annual Revenue/i)).toBeInTheDocument()
  })

  it('shows Security Controls on step 3', async () => {
    renderPage()
    await expectOnStep(1)

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(2)

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(3)
  })

  it('requires security control selection on step 3', async () => {
    renderPage()
    await expectOnStep(1)

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(2)
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(3)

    // Controls default to 'unsure', so the step is always advanceable
    const nextBtn = screen.getByRole('button', { name: /Next/i })
    expect(nextBtn).not.toBeDisabled()
  })

  it('redirects a user who already has an organisation to /settings/organisation without loading it', async () => {
    mockAuthValues.orgId = 1

    renderPage()

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/settings/organisation')
    })
    expect(screen.getByText('Organisation settings')).toBeInTheDocument()
    expect(
      screen.queryByRole('heading', { level: 1, name: 'Set up your organisation' }),
    ).not.toBeInTheDocument()
    // No organisation GET (or any other request) is made by the wizard.
    expect(mockFetchWithAuth).not.toHaveBeenCalled()
  })

  it('stays on step 2 after creating the organisation, and step 2 saves with PUT', async () => {
    renderPage()
    await expectOnStep(1)

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(2)

    // Org created via POST; orgId is now set but the wizard was not redirected.
    expect(mockAuthValues.orgId).toBe(7)
    expect(screen.getByTestId('location')).toHaveTextContent('/onboarding')
    expect(mockFetchWithAuth).toHaveBeenCalledWith(
      expect.stringMatching(/\/onboarding\/complete$/),
      expect.objectContaining({ method: 'POST' }),
    )
    expect(
      mockFetchWithAuth.mock.calls.some(
        ([url, opts]) =>
          /\/organizations\/\d+$/.test(url as string) &&
          (opts as { method?: string })?.method === 'PUT',
      ),
    ).toBe(false)

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(3)

    expect(mockFetchWithAuth).toHaveBeenCalledWith(
      '/api/v1/organizations/7',
      expect.objectContaining({ method: 'PUT' }),
    )
    expect(screen.getByTestId('location')).toHaveTextContent('/onboarding')
  })

  it('sends null, not "", for unset values when step 2 saves after creating with only a name', async () => {
    renderPage()
    await expectOnStep(1)

    fireEvent.change(screen.getByLabelText(/Company Name/i), {
      target: { value: 'Test Corp' },
    })
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(2)
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(3)

    await waitFor(() => {
      const put = mockFetchWithAuth.mock.calls.find(
        ([url, opts]) =>
          /\/organizations\/\d+$/.test(url as string) &&
          (opts as { method?: string })?.method === 'PUT',
      )
      expect(put).toBeDefined()
      const body = JSON.parse((put![1] as { body: string }).body)
      expect(body.name).toBe('Test Corp')
      expect(body.industry_label).toBeNull()
      expect(body.primary_state).toBeNull()
      expect(body.employee_range).toBeNull()
    })
  })

  it('retains form data when navigating back', async () => {
    renderPage()
    await expectOnStep(1)

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(2)

    fireEvent.click(screen.getByRole('button', { name: /Previous/i }))
    await expectOnStep(1)

    const nameInput = screen.getByLabelText(/Company Name/i) as HTMLInputElement
    expect(nameInput.value).toBe('Test Corp')
  })

  it('redirects when the organisation exists once auth finishes loading', async () => {
    // Entry is captured when orgLoading first turns false, so the user had an
    // organisation at entry and is sent to settings.
    mockAuthValues.orgLoading = true
    mockAuthValues.orgId = null

    renderPage()
    await setAuth({ orgLoading: false, orgId: 1 })

    await waitFor(() => {
      expect(screen.getByTestId('location')).toHaveTextContent('/settings/organisation')
    })
  })

  it('stays on the wizard when the organisation is created after entry', async () => {
    // No organisation at entry (orgId null when loading finishes); creating one
    // during step 1 sets orgId but must not redirect the user away mid-wizard.
    mockAuthValues.orgLoading = true
    mockAuthValues.orgId = null

    renderPage()
    await setAuth({ orgLoading: false, orgId: null })
    await expectOnStep(1)
    await setAuth({ orgId: 7 })

    expect(screen.getByTestId('location')).toHaveTextContent('/onboarding')
    expect(
      screen.getByRole('heading', { level: 1, name: 'Set up your organisation' }),
    ).toBeInTheDocument()
  })

  it('navigates to dashboard on form submission', async () => {
    renderPage()
    await expectOnStep(1)

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(2)

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(3)

    selectFirstSecurityControl()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(4)

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(5)

    fireEvent.click(screen.getByRole('button', { name: /Complete/i }))

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/overview')
    })
    expect(completeIntake).toHaveBeenCalledTimes(1)
  })

  it('shows error message on submission failure', async () => {
    // The component PUTs to /api/v1/organizations/{orgId} (not PATCH to /mine).
    // Step 1→2 creates the org (POST); 2→3, 3→4, 4→5 are 3 PUTs + Complete (1 PUT) = 4 total.
    // Fail the 4th PUT so the final submission surfaces the error.
    let putCount = 0
    mockFetchWithAuth.mockImplementation((url: string, options?: Record<string, unknown>) => {
      if (isMainOrgUrl(url) && options?.method === 'PUT') {
        putCount += 1
        if (putCount >= 4) {
          return Promise.resolve({
            ok: false,
            json: async () => ({ detail: 'Validation failed' }),
          })
        }
        return Promise.resolve({ ok: true, json: async () => ({}) })
      }
      return Promise.resolve({ ok: true, json: async () => ({}) })
    })

    renderPage()
    await expectOnStep(1)

    fillStep1()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(2)

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(3)

    selectFirstSecurityControl()
    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(4)

    fireEvent.click(screen.getByRole('button', { name: /Next/i }))
    await expectOnStep(5)

    fireEvent.click(screen.getByRole('button', { name: /Complete/i }))

    await waitFor(() => {
      // Error renders inside `.intake-error` div above the form actions.
      expect(screen.getByText(/Validation failed/i)).toBeInTheDocument()
    })
  })
})

