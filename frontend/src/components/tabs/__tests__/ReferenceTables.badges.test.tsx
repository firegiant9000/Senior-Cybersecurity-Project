import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import IC3Table from '../IC3Table'
import EconomicsTable from '../EconomicsTable'

const { mockFetch } = vi.hoisted(() => ({ mockFetch: vi.fn() }))

vi.mock('../../../api/fetchWithAuth', () => ({
  fetchWithAuth: mockFetch,
}))

vi.mock('../../shared/SourceBadge', () => ({
  default: ({ datasetKey }: { datasetKey: string }) => (
    <span data-testid="source-badge" data-dataset-key={datasetKey} />
  ),
}))

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body })

beforeEach(() => {
  vi.clearAllMocks()
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

describe('IC3Table source badge', () => {
  it('shows one badge once the incidents have loaded, and none while loading', async () => {
    mockFetch.mockImplementation(async (url: string) =>
      url.includes('filter-options')
        ? ok({ attack_types: [], states: [], years: [] })
        : ok({
            total: 1,
            page: 1,
            page_size: 10,
            items: [
              {
                id: 1,
                year: 2023,
                attack_type: 'BEC',
                sector: 'Finance',
                state: 'CA',
                complaint_count: 5,
                loss_amount: 1000,
                avg_loss_per_incident: 200,
              },
            ],
          }),
    )
    render(<IC3Table apiBaseUrl="http://x" datasetKey="ic3_incidents" />)
    expect(screen.queryByTestId('source-badge')).toBeNull()

    const badge = await screen.findByTestId('source-badge')
    expect(badge).toHaveAttribute('data-dataset-key', 'ic3_incidents')
    expect(screen.getAllByTestId('source-badge')).toHaveLength(1)
  })

  it('shows no badge when the fetch fails', async () => {
    mockFetch.mockImplementation(async (url: string) =>
      url.includes('filter-options')
        ? ok({ attack_types: [], states: [], years: [] })
        : { ok: false, status: 500, json: async () => ({}) },
    )
    render(<IC3Table apiBaseUrl="http://x" datasetKey="ic3_incidents" />)
    await screen.findByText(/Error: Failed to fetch IC3 data/)
    expect(screen.queryByTestId('source-badge')).toBeNull()
  })
})

describe('EconomicsTable source badge', () => {
  it('shows one badge once the data has loaded, and none while loading', async () => {
    mockFetch.mockResolvedValue(
      ok({
        total: 1,
        page: 1,
        page_size: 10,
        items: [{ id: 1, state: 'CA', smb_count: 100, avg_revenue: 5000 }],
      }),
    )
    render(<EconomicsTable apiBaseUrl="http://x" datasetKey="bea_economics" />)
    expect(screen.queryByTestId('source-badge')).toBeNull()

    const badge = await screen.findByTestId('source-badge')
    expect(badge).toHaveAttribute('data-dataset-key', 'bea_economics')
    expect(screen.getAllByTestId('source-badge')).toHaveLength(1)
  })

  it('shows no badge when the fetch fails', async () => {
    mockFetch.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) })
    render(<EconomicsTable apiBaseUrl="http://x" datasetKey="bea_economics" />)
    await screen.findByText(/Error: Failed to fetch economics data/)
    expect(screen.queryByTestId('source-badge')).toBeNull()
  })
})
