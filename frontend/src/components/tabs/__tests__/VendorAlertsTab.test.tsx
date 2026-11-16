import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import VendorAlertsTab from '../VendorAlertsTab'

const { mockFetchAlerts } = vi.hoisted(() => ({ mockFetchAlerts: vi.fn() }))

// Stable references: the component's load callback depends on `user`.
const authValue = { user: { id: 1 }, orgId: 1 }
vi.mock('../../../context/AuthContext', () => ({
  useAuth: () => authValue,
}))

vi.mock('../../../api/vendorAlerts', () => ({
  fetchVendorAlerts: mockFetchAlerts,
}))

vi.mock('../../../api/vendors', () => ({
  createVendor: vi.fn(),
  suggestVendors: vi.fn().mockResolvedValue([]),
}))

vi.mock('../../shared/SourceBadge', () => ({
  default: ({ datasetKey }: { datasetKey: string }) => (
    <span data-testid="source-badge" data-dataset-key={datasetKey} />
  ),
}))

const makeResponse = () => ({
  items: [
    {
      cve_id: 'CVE-2026-0001',
      vendor_name: 'Acme',
      kev_product: 'Gateway',
      severity_label: 'High',
      cvss_score: 8.1,
      risk_score: 70,
      due_date: null,
      product_specific: false,
      org_product: null,
    },
  ],
  other_alerts: [],
  unmatched_vendors: [],
  total_matched: 1,
  severity_breakdown: { critical: 0, high: 1, medium: 0, low: 0, unknown: 0 },
  kev_last_ingest_at: null,
  reason: null,
})

describe('VendorAlertsTab source badge', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockFetchAlerts.mockResolvedValue(makeResponse())
  })

  it('labels the tab heading with the vendor_alerts source badge', async () => {
    const { container } = render(
      <MemoryRouter>
        <VendorAlertsTab />
      </MemoryRouter>,
    )
    const heading = await screen.findByRole('heading', { name: /Vendor Alerts/ })

    const badge = container.querySelector('[data-dataset-key="vendor_alerts"]')
    expect(badge).toBeInTheDocument()
    expect(badge?.closest('h2')).toBeNull()
    expect(badge?.parentElement).toBe(heading.parentElement)
    expect(badge?.closest('.vendor-alerts-header')).not.toBeNull()
  })

  it('badges the no-matches state with vendor_alerts', async () => {
    mockFetchAlerts.mockResolvedValue({
      ...makeResponse(),
      items: [],
      total_matched: 0,
      reason: 'no_matches',
    })
    const { container } = render(
      <MemoryRouter>
        <VendorAlertsTab />
      </MemoryRouter>,
    )
    await screen.findByText('No active threats for your stack')

    const badge = container.querySelector('[data-dataset-key="vendor_alerts"]')
    expect(badge).toBeInTheDocument()
    expect(badge?.closest('.vendor-no-matches-card')).not.toBeNull()
  })
})
