import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import IC3Table from '../IC3Table'

const { mockFetchWithAuth } = vi.hoisted(() => ({ mockFetchWithAuth: vi.fn() }))

vi.mock('../../../api/fetchWithAuth', () => ({
  fetchWithAuth: mockFetchWithAuth,
}))

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })

const EMPTY_INCIDENTS = { total: 0, page: 1, page_size: 10, items: [] }
const FILTER_OPTIONS = { attack_types: ['Phishing'], states: ['CA'], years: [2024] }

const routeApi = () => {
  mockFetchWithAuth.mockImplementation((url: string) => {
    if (url.includes('/ic3/filter-options')) {
      return Promise.resolve(jsonResponse(FILTER_OPTIONS))
    }
    return Promise.resolve(jsonResponse(EMPTY_INCIDENTS))
  })
}

describe('IC3Table empty states', () => {
  beforeEach(() => {
    mockFetchWithAuth.mockReset()
    routeApi()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('tells the user no IC3 data has been loaded when no filters are set', async () => {
    const { container } = render(<IC3Table apiBaseUrl="http://api.test" />)

    expect(
      await screen.findByText('No IC3 incident data has been loaded yet.'),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Try widening them/)).not.toBeInTheDocument()
    expect(container.textContent).not.toMatch(/python/i)
    expect(container.querySelector('code')).toBeNull()
  })

  it('asks the user to widen the filters when filters match nothing', async () => {
    const { container } = render(<IC3Table apiBaseUrl="http://api.test" />)

    fireEvent.change(await screen.findByLabelText('Attack Type'), {
      target: { value: 'Phishing' },
    })

    await waitFor(() =>
      expect(
        screen.getByText('No IC3 incidents match these filters. Try widening them.'),
      ).toBeInTheDocument(),
    )
    expect(screen.queryByText('No IC3 incident data has been loaded yet.')).not.toBeInTheDocument()
    expect(container.textContent).not.toMatch(/python/i)
    expect(container.querySelector('code')).toBeNull()
  })
})
