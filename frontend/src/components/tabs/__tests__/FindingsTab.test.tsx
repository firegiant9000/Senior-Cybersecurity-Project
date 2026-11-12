import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import FindingsTab from '../FindingsTab'

const { mockFetchFindings, mockFetchHistory, mockPatchStatus } = vi.hoisted(() => ({
  mockFetchFindings: vi.fn(),
  mockFetchHistory: vi.fn(),
  mockPatchStatus: vi.fn(),
}))

// Stable reference: the component's load callback depends on `user`.
const authValue = { user: { id: 1 } }
vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => authValue,
}))

vi.mock('../../../api/findings', () => ({
  fetchFindings: mockFetchFindings,
  fetchFindingsHistory: mockFetchHistory,
  patchFindingStatus: mockPatchStatus,
}))

const makeFinding = (over: Record<string, unknown>) => ({
  id: 'id-1',
  stable_key: 'key-1',
  finding_type: 'threat_exposure',
  severity: 'high',
  severity_score: 70,
  title: 'Finding one',
  description: 'Description one',
  evidence: {},
  source: 'kev',
  affected_assets: [],
  status: 'open',
  ...over,
})

const makeReport = (findings: ReturnType<typeof makeFinding>[]) => ({
  org_id: 1,
  findings,
  summary: {
    total: findings.length,
    by_type: findings.reduce<Record<string, number>>((acc, f) => {
      const t = f.finding_type as string
      acc[t] = (acc[t] ?? 0) + 1
      return acc
    }, {}),
    by_severity: { high: findings.length },
  },
  generated_at: '2026-01-01T12:00:00Z',
  data_sources_used: ['kev'],
  assessment_tier: 'enhanced',
})

const twoFindings = () =>
  makeReport([
    makeFinding({ id: 'a', stable_key: 'key-a', title: 'Threat alpha' }),
    makeFinding({
      id: 'b',
      stable_key: 'key-b',
      finding_type: 'recommended_action',
      title: 'Action beta',
    }),
  ])

const renderTab = () =>
  render(
    <MemoryRouter>
      <FindingsTab />
    </MemoryRouter>,
  )

// The component holds a loading screen for at least 1.2s, so allow for it.
const SLOW = { timeout: 4000 }

const profileLinks = () =>
  screen.getAllByRole('link').filter((l) => l.getAttribute('href') === '/org-profile')

describe('FindingsTab characterisation', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchHistory.mockResolvedValue({ items: [], total: 0 })
    mockPatchStatus.mockResolvedValue({ stable_key: 'key-a', status: 'done' })
  })

  it('renders findings grouped by type from fetchFindings', async () => {
    mockFetchFindings.mockResolvedValue(twoFindings())
    renderTab()

    expect(await screen.findByText('Threat alpha', {}, SLOW)).toBeInTheDocument()
    expect(mockFetchFindings).toHaveBeenCalledTimes(1)
    expect(screen.getByText('Action beta')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Threats Targeting You/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /What to Do Next/ })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: /Missing Information/ })).not.toBeInTheDocument()
  })

  it('checking a finding calls patchFindingStatus with stable key, new status and meta', async () => {
    mockFetchFindings.mockResolvedValue(twoFindings())
    renderTab()
    await screen.findByText('Threat alpha', {}, SLOW)

    const box = screen.getByRole('checkbox', { name: 'Mark "Threat alpha" as remediated' })
    expect(box).not.toBeChecked()
    fireEvent.click(box)

    await waitFor(() =>
      expect(mockPatchStatus).toHaveBeenCalledWith('key-a', 'done', {
        title: 'Threat alpha',
        severity: 'high',
      }),
    )
    expect(
      await screen.findByRole('checkbox', { name: 'Mark "Threat alpha" as open' }),
    ).toBeChecked()
  })

  it('unchecking a done finding sends status open', async () => {
    const report = makeReport([
      makeFinding({ id: 'a', stable_key: 'key-a', title: 'Threat alpha', status: 'done' }),
    ])
    mockFetchFindings.mockResolvedValue(report)
    mockPatchStatus.mockResolvedValue({ stable_key: 'key-a', status: 'open' })
    renderTab()
    await screen.findByText('Threat alpha', {}, SLOW)

    fireEvent.click(screen.getByRole('checkbox', { name: 'Mark "Threat alpha" as open' }))

    await waitFor(() =>
      expect(mockPatchStatus).toHaveBeenCalledWith('key-a', 'open', {
        title: 'Threat alpha',
        severity: 'high',
      }),
    )
  })

  it('the Scan History toggle fetches history with a limit of 10', async () => {
    mockFetchFindings.mockResolvedValue(twoFindings())
    renderTab()
    await screen.findByText('Threat alpha', {}, SLOW)
    expect(mockFetchHistory).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: /Scan History/ }))

    await waitFor(() =>
      expect(mockFetchHistory).toHaveBeenCalledWith(expect.any(AbortSignal), 10),
    )
    expect(await screen.findByText('No previous scans recorded yet.')).toBeInTheDocument()
  })

  it('links to /org-profile from the empty state', async () => {
    mockFetchFindings.mockResolvedValue(makeReport([]))
    renderTab()

    await screen.findByText('No Findings', {}, SLOW)
    expect(profileLinks()).toHaveLength(1)
  })

  it('links to /org-profile from the setup-required error state', async () => {
    mockFetchFindings.mockRejectedValue(new Error('Profile is incomplete'))
    renderTab()

    await screen.findByText('Setup Required', {}, SLOW)
    expect(profileLinks()).toHaveLength(1)
  })

  it('links to /org-profile and offers Retry from the generic error state', async () => {
    mockFetchFindings.mockRejectedValue(new Error('boom'))
    renderTab()

    await screen.findByText("Couldn't Load Findings", {}, SLOW)
    expect(profileLinks()).toHaveLength(1)
    expect(screen.getByText(/Details: boom/)).toBeInTheDocument()

    mockFetchFindings.mockResolvedValue(twoFindings())
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(await screen.findByText('Threat alpha', {}, SLOW)).toBeInTheDocument()
    expect(mockFetchFindings).toHaveBeenCalledTimes(2)
  })
})
