import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import AISummaryTab from '../AISummaryTab'

// Stable references: the component's load callback depends on `user`.
const authValue = { user: { uid: 'user-1' } }
vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => authValue,
}))

const userContextValue = { organization: { name: 'Acme Ltd' } }
vi.mock('../../../context/UserContext', () => ({
  useUserContext: () => userContextValue,
}))

// The real api/aiSummary + api/fetchWithAuth run; only Firebase and the network are stubbed.
vi.mock('../../../firebase', () => ({
  auth: { currentUser: null },
}))

const SUMMARY_PATH = '/api/v1/organizations/mine/ai-summary'

const makeSummary = (over: Record<string, unknown> = {}) => ({
  narrative: 'Your external exposure is moderate.\nPatch the VPN appliance first.',
  ai_generated: true,
  model_used: 'test-model',
  findings_count: 4,
  risk_score: 61,
  risk_label: 'High',
  generated_at: '2026-01-01T12:00:00Z',
  cached: false,
  disclaimer: 'Test disclaimer text.',
  posture_statement: 'Posture is fair.',
  notable_risks: [
    { title: 'Exposed VPN gateway', severity: 'critical', context: 'Known exploited flaw.' },
  ],
  data_gaps: null,
  next_steps: null,
  ...over,
})

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

const fetchMock = vi.fn()

// Route by URL: history is always an empty list; the summary is supplied per test.
const routeFetch = (summary: () => Response) => {
  fetchMock.mockImplementation((url: string) => {
    if (url.includes('/ai-summary/history')) {
      return Promise.resolve(jsonResponse({ items: [], total: 0, limit: 10, offset: 0 }))
    }
    return Promise.resolve(summary())
  })
}

const summaryCalls = () =>
  fetchMock.mock.calls
    .map((c) => c[0] as string)
    .filter((u) => u.includes(SUMMARY_PATH) && !u.includes('/history') && !u.includes('/feedback'))

const renderTab = () =>
  render(
    <MemoryRouter>
      <AISummaryTab />
    </MemoryRouter>,
  )

// The component enforces a 1.5 s minimum loading time: real timers, longer timeout.
const FIND_TIMEOUT = { timeout: 5000 }

describe('AISummaryTab (characterisation)', () => {
  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('renders the narrative and notable risks from the API', async () => {
    routeFetch(() => jsonResponse(makeSummary()))
    renderTab()

    expect(await screen.findByText('Your external exposure is moderate.', {}, FIND_TIMEOUT)).toBeInTheDocument()
    expect(screen.getByText('Patch the VPN appliance first.')).toBeInTheDocument()
    expect(screen.getByText('Exposed VPN gateway')).toBeInTheDocument()
    expect(screen.getByText('Known exploited flaw.')).toBeInTheDocument()
    expect(screen.getByText('critical')).toBeInTheDocument()
    expect(summaryCalls()).toHaveLength(1)
    expect(summaryCalls()[0]).toMatch(new RegExp(`${SUMMARY_PATH}$`))
  })

  it('Regenerate requests the summary again with force_refresh=true', async () => {
    routeFetch(() => jsonResponse(makeSummary()))
    renderTab()

    fireEvent.click(await screen.findByRole('button', { name: /^regenerate$/i }, FIND_TIMEOUT))

    await waitFor(() => expect(summaryCalls()).toHaveLength(2))
    expect(summaryCalls()[1]).toContain(`${SUMMARY_PATH}?force_refresh=true`)
    // Back to the content once the refreshed summary arrives.
    expect(await screen.findByText('Exposed VPN gateway', {}, FIND_TIMEOUT)).toBeInTheDocument()
  }, 15000)

  it('a 422 shows the profile prompt linking to /settings/organisation', async () => {
    routeFetch(() =>
      jsonResponse(
        {
          detail:
            'Your organization profile needs at least Enhanced tier ' +
            '(add vendors, domains, and security controls) before generating an AI summary.',
        },
        422,
      ),
    )
    renderTab()

    expect(await screen.findByText('Setup Required', {}, FIND_TIMEOUT)).toBeInTheDocument()
    const link = document.querySelector('a[href="/settings/organisation"]')
    expect(link).not.toBeNull()
    // No narrative is rendered in this state.
    expect(screen.queryByText('Your external exposure is moderate.')).not.toBeInTheDocument()
  })

  it('the Print button calls window.print', async () => {
    routeFetch(() => jsonResponse(makeSummary()))
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {})
    renderTab()

    fireEvent.click(await screen.findByRole('button', { name: /print/i }, FIND_TIMEOUT))

    expect(printSpy).toHaveBeenCalledTimes(1)
  })
})
