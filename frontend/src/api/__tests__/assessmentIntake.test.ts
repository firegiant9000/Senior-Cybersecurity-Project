import { describe, it, expect, vi, beforeEach } from 'vitest'
import { fetchAssessmentIntake } from '../assessmentIntake'
import type { AssessmentIntakeResponse } from '../assessmentIntake'

// Mock fetchWithAuth
const mockGetJsonAuth = vi.fn()
vi.mock('../fetchWithAuth', () => ({
  API_BASE_URL: 'https://api.test',
  getJsonAuth: (...args: unknown[]) => mockGetJsonAuth(...args),
}))

describe('assessmentIntake API', () => {
  beforeEach(() => {
    mockGetJsonAuth.mockClear()
  })

  const mockResponse: AssessmentIntakeResponse = {
    current_tier: 'basic',
    tiers: [
      {
        tier: 'basic',
        label: 'Basic',
        description: 'Basic assessment',
        requirements: [
          {
            key: 'name',
            label: 'Company Name',
            met: true,
            detail: 'Required',
          },
          {
            key: 'industry',
            label: 'Industry',
            met: true,
            detail: 'Required',
          },
        ],
        all_met: true,
        unlocks: ['risk_scores'],
      },
      {
        tier: 'enhanced',
        label: 'Enhanced',
        description: 'Enhanced assessment',
        requirements: [
          {
            key: 'security_controls',
            label: 'Security Controls',
            met: false,
            detail: 'Pending',
          },
        ],
        all_met: false,
        unlocks: ['findings'],
      },
    ],
    next_tier: 'enhanced',
    next_tier_progress: 33.33,
    fields_to_advance: ['security_controls'],
  }

  it('fetches assessment intake data from correct endpoint', async () => {
    mockGetJsonAuth.mockResolvedValue(mockResponse)
    const signal = new AbortController().signal

    const result = await fetchAssessmentIntake(signal)

    expect(mockGetJsonAuth).toHaveBeenCalledWith(
      'https://api.test/api/v1/organizations/mine/intake',
      signal,
    )
    expect(result).toEqual(mockResponse)
  })

  it('returns assessment intake response with all required fields', async () => {
    mockGetJsonAuth.mockResolvedValue(mockResponse)
    const signal = new AbortController().signal

    const result = await fetchAssessmentIntake(signal)

    expect(result.current_tier).toBe('basic')
    expect(result.next_tier).toBe('enhanced')
    expect(result.next_tier_progress).toBe(33.33)
    expect(result.tiers).toHaveLength(2)
    expect(result.fields_to_advance).toContain('security_controls')
  })

  it('passes abort signal correctly to getJsonAuth', async () => {
    mockGetJsonAuth.mockResolvedValue(mockResponse)
    const controller = new AbortController()
    const signal = controller.signal

    const promise = fetchAssessmentIntake(signal)

    expect(mockGetJsonAuth).toHaveBeenCalledWith(
      expect.any(String),
      signal,
    )

    const result = await promise
    expect(result).toBeDefined()
  })

  it('handles tier definition structure correctly', async () => {
    mockGetJsonAuth.mockResolvedValue(mockResponse)
    const signal = new AbortController().signal

    const result = await fetchAssessmentIntake(signal)

    const basicTier = result.tiers[0]
    expect(basicTier).toHaveProperty('tier')
    expect(basicTier).toHaveProperty('label')
    expect(basicTier).toHaveProperty('description')
    expect(basicTier).toHaveProperty('requirements')
    expect(basicTier).toHaveProperty('all_met')
    expect(basicTier).toHaveProperty('unlocks')
  })

  it('handles empty fields_to_advance when all requirements are met', async () => {
    const responseWithoutFields: AssessmentIntakeResponse = {
      ...mockResponse,
      current_tier: 'comprehensive',
      next_tier: null,
      fields_to_advance: [],
    }
    mockGetJsonAuth.mockResolvedValue(responseWithoutFields)
    const signal = new AbortController().signal

    const result = await fetchAssessmentIntake(signal)

    expect(result.fields_to_advance).toEqual([])
    expect(result.next_tier).toBe(null)
  })

  it('handles null next_tier for comprehensive tier', async () => {
    const comprehensiveResponse: AssessmentIntakeResponse = {
      current_tier: 'comprehensive',
      tiers: [
        {
          tier: 'comprehensive',
          label: 'Comprehensive',
          description: 'Full assessment',
          requirements: [],
          all_met: true,
          unlocks: ['all_features'],
        },
      ],
      next_tier: null,
      next_tier_progress: 0,
      fields_to_advance: [],
    }
    mockGetJsonAuth.mockResolvedValue(comprehensiveResponse)
    const signal = new AbortController().signal

    const result = await fetchAssessmentIntake(signal)

    expect(result.next_tier).toBeNull()
    expect(result.next_tier_progress).toBe(0)
  })

  it('handles requirement detail messages', async () => {
    mockGetJsonAuth.mockResolvedValue(mockResponse)
    const signal = new AbortController().signal

    const result = await fetchAssessmentIntake(signal)

    const requirement = result.tiers[0].requirements[0]
    expect(requirement.detail).toBe('Required')
    expect(requirement.label).toBe('Company Name')
  })

  it('propagates errors from getJsonAuth', async () => {
    const error = new Error('API Error')
    mockGetJsonAuth.mockRejectedValue(error)
    const signal = new AbortController().signal

    await expect(fetchAssessmentIntake(signal)).rejects.toThrow('API Error')
  })

  it('handles network errors', async () => {
    const networkError = new Error('Network failed')
    mockGetJsonAuth.mockRejectedValue(networkError)
    const signal = new AbortController().signal

    await expect(fetchAssessmentIntake(signal)).rejects.toThrow('Network failed')
  })
})
