import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  getAssetFindings,
  patchAssetFindingStatus,
  type AssetFindingsResponse,
} from '../assets'

// Mock fetchWithAuth — the findings calls use it directly.
const mockFetchWithAuth = vi.fn()
vi.mock('../fetchWithAuth', () => ({
  API_BASE_URL: 'https://api.test',
  fetchWithAuth: (...args: unknown[]) => mockFetchWithAuth(...args),
}))

function okJson(body: unknown) {
  return { ok: true, json: () => Promise.resolve(body) }
}

function errJson(detail: string) {
  return { ok: false, json: () => Promise.resolve({ detail }) }
}

const findingsResponse: AssetFindingsResponse = {
  asset_id: 7,
  total: 1,
  items: [
    {
      finding_id: 11,
      software_id: 3,
      vendor: 'Apache',
      product: 'log4j',
      version: '2.14.1',
      cve_id: 'CVE-2021-44228',
      cvss_score: 10.0,
      epss_score: 0.97,
      severity: 'CRITICAL',
      in_kev: true,
      match_confidence: 'high',
      risk_score: 98.5,
      risk_tier: 'Critical',
      status: 'open',
      remediation_summary: 'Upgrade to 2.17.1',
      description: 'Log4Shell',
    },
  ],
  note: 'version-aware',
}

describe('asset findings API', () => {
  beforeEach(() => {
    mockFetchWithAuth.mockClear()
  })

  it('GETs findings without a refresh query by default', async () => {
    mockFetchWithAuth.mockResolvedValue(okJson(findingsResponse))

    const result = await getAssetFindings(1, 7)

    expect(mockFetchWithAuth).toHaveBeenCalledWith(
      'https://api.test/api/v1/organizations/1/assets/7/findings',
    )
    expect(result.items[0].match_confidence).toBe('high')
    expect(result.items[0].risk_tier).toBe('Critical')
  })

  it('appends ?refresh=true when refresh is requested', async () => {
    mockFetchWithAuth.mockResolvedValue(okJson(findingsResponse))

    await getAssetFindings(1, 7, { refresh: true })

    expect(mockFetchWithAuth).toHaveBeenCalledWith(
      'https://api.test/api/v1/organizations/1/assets/7/findings?refresh=true',
    )
  })

  it('throws the API detail when findings load fails', async () => {
    mockFetchWithAuth.mockResolvedValue(errJson('boom'))

    await expect(getAssetFindings(1, 7)).rejects.toThrow('boom')
  })

  it('PATCHes finding status to the correct URL with status + remediation', async () => {
    mockFetchWithAuth.mockResolvedValue(
      okJson({ finding_id: 11, status: 'false_positive' }),
    )

    const result = await patchAssetFindingStatus(
      1,
      7,
      11,
      'false_positive',
      'not installed in prod',
    )

    expect(mockFetchWithAuth).toHaveBeenCalledTimes(1)
    const [url, init] = mockFetchWithAuth.mock.calls[0]
    expect(url).toBe(
      'https://api.test/api/v1/organizations/1/assets/7/findings/11/status',
    )
    expect(init.method).toBe('PATCH')
    expect(JSON.parse(init.body)).toEqual({
      status: 'false_positive',
      remediation_summary: 'not installed in prod',
    })
    expect(result.status).toBe('false_positive')
  })

  it('omits remediation_summary from the body when none is supplied', async () => {
    mockFetchWithAuth.mockResolvedValue(okJson({ finding_id: 11, status: 'open' }))

    await patchAssetFindingStatus(1, 7, 11, 'open')

    const [, init] = mockFetchWithAuth.mock.calls[0]
    // The key must be absent (not null) so the backend preserves any existing
    // reviewer remediation note rather than clearing it.
    expect(Object.prototype.hasOwnProperty.call(JSON.parse(init.body), 'remediation_summary')).toBe(
      false,
    )
  })

  it('throws the API detail when the status PATCH fails', async () => {
    mockFetchWithAuth.mockResolvedValue(errJson('invalid status'))

    await expect(
      patchAssetFindingStatus(1, 7, 11, 'fixed'),
    ).rejects.toThrow('invalid status')
  })
})
