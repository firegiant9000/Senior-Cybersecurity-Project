import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
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
  default: ({ datasetKey }: { datasetKey: string }) => (
    <span data-testid="source-badge" data-dataset-key={datasetKey} />
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
  it('labels the report with the executive_summary source badge', async () => {
    const { container } = render(
      <MemoryRouter>
        <ExecutiveReportPage />
      </MemoryRouter>,
    )
    await screen.findByRole('heading', { name: /Risk Snapshot/ })

    const badge = container.querySelector('[data-dataset-key="executive_summary"]')
    expect(badge).toBeInTheDocument()
    expect(badge?.closest('h2')).not.toBeNull()
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
