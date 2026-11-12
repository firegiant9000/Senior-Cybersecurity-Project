import { describe, it, expect, vi, beforeEach } from 'vitest'
import { updateOrganization } from '../organizations'

const mockFetchWithAuth = vi.fn()
vi.mock('../fetchWithAuth', () => ({
  API_BASE_URL: 'https://api.test',
  fetchWithAuth: (...args: unknown[]) => mockFetchWithAuth(...args),
}))

describe('organizations API', () => {
  beforeEach(() => {
    mockFetchWithAuth.mockReset()
  })

  it('PUTs the body as JSON to the organisation URL', async () => {
    mockFetchWithAuth.mockResolvedValue({ ok: true })
    const body = { name: 'Acme', logo_url: null, industry_label: 'Retail' }

    await updateOrganization(7, body)

    expect(mockFetchWithAuth).toHaveBeenCalledTimes(1)
    const [url, init] = mockFetchWithAuth.mock.calls[0]
    expect(url).toBe('https://api.test/api/v1/organizations/7')
    expect(init.method).toBe('PUT')
    expect(init.headers).toEqual({ 'Content-Type': 'application/json' })
    expect(init.body).toBe(JSON.stringify(body))
  })

  it('throws Error(detail) from the response text on a non-OK response', async () => {
    mockFetchWithAuth.mockResolvedValue({
      ok: false,
      text: () => Promise.resolve('Name already taken'),
    })

    await expect(updateOrganization(7, { name: 'Acme' })).rejects.toThrow(
      'Name already taken',
    )
  })

  it('throws a generic Error when a non-OK response has no body', async () => {
    mockFetchWithAuth.mockResolvedValue({
      ok: false,
      text: () => Promise.resolve(''),
    })

    await expect(updateOrganization(7, { name: 'Acme' })).rejects.toThrow(
      'Failed to save organisation',
    )
  })
})
