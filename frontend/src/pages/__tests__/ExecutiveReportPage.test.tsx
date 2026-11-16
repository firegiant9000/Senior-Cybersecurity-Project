import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import ExecutiveReportPage from '../ExecutiveReportPage'

const { mockSummary, mockLoss, mockFindings } = vi.hoisted(() => ({
  mockSummary: vi.fn(),
  mockLoss: vi.fn(),
  mockFindings: vi.fn(),
}))

const authValue = { user: { email: 'a@example.com' } }
vi.mock('../../context/AuthContext', () => ({
  useAuth: () => authValue,
}))

vi.mock('../../api/executiveSummary', () => ({
  fetchExecutiveSummary: mockSummary,
}))
vi.mock('../../api/lossProjection', () => ({
  fetchLossProjection: mockLoss,
}))
vi.mock('../../api/findings', () => ({
  fetchFindings: mockFindings,
}))

vi.mock('../../components/shared/SourceBadge', () => ({
  default: ({ datasetKey, datasetKeys }: { datasetKey?: string; datasetKeys?: string[] }) => (
    <span data-testid="source-badge" data-dataset-key={datasetKey ?? datasetKeys?.join(',')} />
  ),
}))

beforeEach(() => {
  vi.clearAllMocks()
  mockSummary.mockResolvedValue({
    generated_at: '2026-01-01T00:00:00Z',
    data_year_range: '2020-2024',
    confidence_level: 'medium',
    risk_score: 50,
    risk_label: 'Moderate',
    loss_estimate_formatted: '$1M',
    kev_count: 10,
    critical_cve_count: 5,
    top_threats: [],
    methodology: 'm',
    disclaimer: 'd',
  })
  mockLoss.mockResolvedValue({ has_data: false })
  mockFindings.mockResolvedValue(null)
})

describe('ExecutiveReportPage source badge', () => {
  it('labels Risk Snapshot with the least confident of its inputs (static IC3)', async () => {
    const { container } = render(
      <MemoryRouter>
        <ExecutiveReportPage />
      </MemoryRouter>,
    )
    const heading = await screen.findByRole('heading', { name: 'Risk Snapshot' })

    const badge = container.querySelector('[data-dataset-key="executive_summary,ic3_incidents"]')
    expect(badge).toBeInTheDocument()
    expect(badge?.closest('h2')).toBeNull()
    expect(badge?.closest('section')).toBe(heading.closest('section'))
  })

  it('labels Most Costly Attack Types with the ic3_incidents badge', async () => {
    mockSummary.mockResolvedValue({
      ...(await mockSummary()),
      top_threats: [{ name: 'BEC', complaint_count: 10, total_loss: 1000 }],
    })
    const { container } = render(
      <MemoryRouter>
        <ExecutiveReportPage />
      </MemoryRouter>,
    )
    const heading = await screen.findByRole('heading', { name: 'Most Costly Attack Types' })

    const badge = container.querySelector('[data-dataset-key="ic3_incidents"]')
    expect(badge).toBeInTheDocument()
    expect(badge?.closest('h2')).toBeNull()
    expect(badge?.closest('section')).toBe(heading.closest('section'))
  })

  it('labels the Projected Annual Loss section with the loss_projection badge', async () => {
    mockLoss.mockResolvedValue({
      has_data: true,
      projected_annual_loss_formatted: '$50K',
      sector: 'retail',
      state: null,
      employee_range: null,
      confidence_level: 'low',
      ic3_data_years: null,
      ic3_incident_count: null,
      ic3_avg_loss_per_incident: null,
      size_multiplier: 1,
      methodology: 'm',
    })
    const { container } = render(
      <MemoryRouter>
        <ExecutiveReportPage />
      </MemoryRouter>,
    )
    const heading = await screen.findByRole('heading', { name: 'Projected Annual Loss' })

    const badge = container.querySelector('[data-dataset-key="loss_projection"]')
    expect(badge).toBeInTheDocument()
    expect(badge?.closest('h2')).toBeNull()
    expect(badge?.closest('section')).toBe(heading.closest('section'))
  })

  it('shows no badge while the report is still generating', () => {
    mockSummary.mockReturnValue(new Promise(() => {}))
    const { container } = render(
      <MemoryRouter>
        <ExecutiveReportPage />
      </MemoryRouter>,
    )
    expect(container.querySelector('[data-dataset-key]')).toBeNull()
  })
})
