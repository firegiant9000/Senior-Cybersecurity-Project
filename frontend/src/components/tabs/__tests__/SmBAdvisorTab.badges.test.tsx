import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import SmBAdvisorTab from '../SmBAdvisorTab'

const mocks = vi.hoisted(() => ({
  fetchIndustryRisk: vi.fn(),
  fetchAttackTypes: vi.fn(),
  fetchSectorAttackMatrix: vi.fn(),
  fetchGeographicHeatmap: vi.fn(),
  fetchSmbRiskScore: vi.fn(),
}))

vi.mock('../../../api/dashboardSummary', () => ({
  fetchIndustryRisk: mocks.fetchIndustryRisk,
  fetchAttackTypes: mocks.fetchAttackTypes,
  fetchSectorAttackMatrix: mocks.fetchSectorAttackMatrix,
  fetchGeographicHeatmap: mocks.fetchGeographicHeatmap,
}))

vi.mock('../../../api/smbRiskScore', () => ({
  fetchSmbRiskScore: mocks.fetchSmbRiskScore,
}))

// Stable reference: the tab auto-fills sector/state from the org profile.
const userContextValue = {
  organization: { industry_label: 'Healthcare', primary_state: 'TX' },
}
vi.mock('../../../context/UserContext', () => ({
  useUserContext: () => userContextValue,
}))

vi.mock('../../shared/SourceBadge', () => ({
  default: ({ datasetKey, datasetKeys }: { datasetKey?: string; datasetKeys?: string[] }) => (
    <span data-testid="source-badge" data-dataset-key={datasetKeys ? datasetKeys.join(',') : datasetKey} />
  ),
}))

describe('SmBAdvisorTab source badges', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.fetchIndustryRisk.mockResolvedValue({
      items: [
        { sector: 'Healthcare', complaint_count: 1200, total_loss: 5_000_000, avg_loss_per_incident: 4000 },
        { sector: 'Retail', complaint_count: 300, total_loss: 900_000, avg_loss_per_incident: 3000 },
      ],
      year: 2025,
    })
    mocks.fetchAttackTypes.mockResolvedValue({ items: [], year: 2025 })
    mocks.fetchSectorAttackMatrix.mockResolvedValue({
      items: [
        {
          sector: 'Healthcare',
          attack_type: 'Phishing',
          complaint_count: 50,
          total_loss: 100000,
          avg_loss_per_incident: 2000,
        },
      ],
      year: 2025,
    })
    mocks.fetchGeographicHeatmap.mockResolvedValue({ items: [], year: 2025 })
    mocks.fetchSmbRiskScore.mockResolvedValue(null)
  })

  const renderTab = () =>
    render(
      <MemoryRouter>
        <SmBAdvisorTab />
      </MemoryRouter>,
    )

  const within = (container: HTMLElement, selector: string, key: string) =>
    container.querySelector(`${selector} [data-dataset-key="${key}"]`)

  it('badges the sector-profile stats with ic3_incidents', async () => {
    const { container } = renderTab()
    await screen.findByText('Reported incidents')

    expect(within(container, '.smb-risk-grade-card', 'ic3_incidents')).toBeInTheDocument()
  })

  it('badges top threats with the sector x attack matrix it is fed by', async () => {
    const { container } = renderTab()
    await screen.findByText('Reported incidents')

    expect(
      within(container, '.smb-threats-card', 'ic3_sector_attack_matrix'),
    ).toBeInTheDocument()
    expect(within(container, '.smb-threats-card', 'ic3_incidents')).toBeNull()
  })

  it('badges the state risk card with ic3_geographic once a state has data', async () => {
    mocks.fetchGeographicHeatmap.mockResolvedValue({
      items: [{ state: 'TX', complaint_count: 10, total_loss: 250000, avg_loss_per_incident: 25000 }],
      year: 2025,
    })
    const { container } = renderTab()
    await screen.findByText('State rank (higher = more losses)')

    expect(within(container, '.smb-state-card', 'ic3_geographic')).toBeInTheDocument()
  })

  it('does not badge the state risk card when no state is selected or data is missing', async () => {
    const { container } = renderTab()
    await screen.findByText('Typical loss')

    expect(container.querySelector('.smb-state-card [data-testid="source-badge"]')).toBeNull()
  })

  it('badges the org risk score with the static org_risk_score key', async () => {
    mocks.fetchSmbRiskScore.mockResolvedValue({
      score: 50,
      effective_score: 45,
      remediation_credit: { done_count: 0, raw_points: 0, applied_points: 0, items: [] },
      industry_exposure: { sector: 'Healthcare', items: [], industry_score: 50 },
      size_factor: { employee_range: '11-50', incident_rate: 1, size_score: 25 },
      breakdown: [],
      methodology: 'm',
      generated_at: '2026-01-01T00:00:00Z',
    })
    const { container } = renderTab()
    await screen.findByText('Typical loss')

    expect(await screen.findByText(/out of 100/)).toBeInTheDocument()
    expect(within(container, '.smb-org-risk-card', 'org_risk_score')).toBeInTheDocument()
  })

  it('does not badge the org risk score when there is no score to show', async () => {
    const { container } = renderTab()
    await screen.findByText('Typical loss')

    expect(container.querySelector('.smb-org-risk-card')).not.toBeNull()
    expect(container.querySelector('.smb-org-risk-card [data-testid="source-badge"]')).toBeNull()
  })

  it('does not badge the org risk score when loading it fails', async () => {
    mocks.fetchSmbRiskScore.mockRejectedValue(new Error('nope'))
    const { container } = renderTab()
    await screen.findByText('Typical loss')

    expect(container.querySelector('[data-dataset-key="org_risk_score"]')).toBeNull()
  })

  it('badges the cost band with ic3_incidents and loss_projection together', async () => {
    const { container } = renderTab()
    await screen.findByText('Typical loss')

    expect(
      within(container, '.smb-cost-card', 'ic3_incidents,loss_projection'),
    ).toBeInTheDocument()
  })

  it('does not badge the Action Plan (advice, not data)', async () => {
    const { container } = renderTab()
    await screen.findByText('Typical loss')

    const heading = screen.getByRole('heading', { name: /Your Action Plan/ })
    const card = heading.closest('.card')
    expect(card).not.toBeNull()
    expect(card?.querySelector('[data-testid="source-badge"]')).toBeNull()
    expect(container.querySelectorAll('[data-testid="source-badge"]').length).toBeGreaterThan(0)
  })
})
