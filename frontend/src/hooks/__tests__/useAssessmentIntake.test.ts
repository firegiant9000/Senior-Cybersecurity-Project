import { renderHook, waitFor, act } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

// Mock auth context FIRST. Return a stable user reference so the hook's
// useEffect dependency array doesn't churn on every render.
const mockAuthState: { user: { uid: string; email: string } | null } = {
  user: { uid: 'u1', email: 'test@example.com' },
}
vi.mock('../../context/AuthContext', () => ({
  useAuth: vi.fn(() => mockAuthState),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}))

// Mock the API
const mockFetchAssessmentIntake = vi.fn()
vi.mock('../../api/assessmentIntake', () => ({
  fetchAssessmentIntake: (...args: unknown[]) => mockFetchAssessmentIntake(...args),
}))

import { useAssessmentIntake } from '../useAssessmentIntake'
import type { AssessmentIntakeResponse } from '../../api/assessmentIntake'

describe('useAssessmentIntake', () => {
  beforeEach(() => {
    mockFetchAssessmentIntake.mockClear()
  })

  const mockData: AssessmentIntakeResponse = {
    current_tier: 'enhanced',
    tiers: [
      {
        tier: 'basic',
        label: 'Basic',
        description: 'Basic tier',
        requirements: [],
        all_met: true,
        unlocks: ['feature1'],
      },
      {
        tier: 'enhanced',
        label: 'Enhanced',
        description: 'Enhanced tier',
        requirements: [],
        all_met: true,
        unlocks: ['feature2'],
      },
    ],
    next_tier: 'comprehensive',
    next_tier_progress: 50,
    fields_to_advance: ['revenue_range'],
  }

  it('returns initial loading state', async () => {
    mockFetchAssessmentIntake.mockImplementation(() => new Promise(() => {})) // Never resolves
    const { result } = renderHook(() => useAssessmentIntake())

    // Initial render might have loading false, wait for it to become true
    await waitFor(() => {
      expect(result.current.loading).toBe(true)
    })
    expect(result.current.data).toBe(null)
    expect(result.current.error).toBe(null)
  })

  it('loads and returns assessment data successfully', async () => {
    mockFetchAssessmentIntake.mockResolvedValue(mockData)
    const { result } = renderHook(() => useAssessmentIntake())

    expect(result.current.loading).toBe(true)

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toEqual(mockData)
    expect(result.current.error).toBe(null)
  })

  it('handles fetch errors gracefully', async () => {
    const error = new Error('Network error')
    mockFetchAssessmentIntake.mockRejectedValue(error)
    const { result } = renderHook(() => useAssessmentIntake())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toBe(null)
    expect(result.current.error).toBe('Network error')
  })

  it('handles non-Error rejection values', async () => {
    mockFetchAssessmentIntake.mockRejectedValue('Unknown error')
    const { result } = renderHook(() => useAssessmentIntake())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.data).toBe(null)
    expect(result.current.error).toBe('Failed to load assessment intake')
  })

  it('provides a refresh function to refetch data', async () => {
    mockFetchAssessmentIntake.mockResolvedValue(mockData)
    const { result, rerender } = renderHook(() => useAssessmentIntake())

    // Wait for initial load
    await waitFor(() => {
      expect(result.current.data).toEqual(mockData)
    })

    expect(mockFetchAssessmentIntake).toHaveBeenCalledTimes(1)

    // Call refresh
    result.current.refresh()
    rerender()

    // Wait for second load
    await waitFor(() => {
      expect(mockFetchAssessmentIntake).toHaveBeenCalledTimes(2)
    })
  })

  it('aborts fetch on unmount', async () => {
    const abortSpy = vi.fn()
    mockFetchAssessmentIntake.mockImplementation((signal: AbortSignal) => {
      signal.addEventListener('abort', abortSpy)
      return new Promise(() => {}) // Never resolves
    })

    const { unmount } = renderHook(() => useAssessmentIntake())

    unmount()

    await waitFor(() => {
      expect(abortSpy).toHaveBeenCalled()
    })
  })

  it('clears data and error when user is not logged in', async () => {
    const original = mockAuthState.user
    mockAuthState.user = null
    try {
      const { result } = renderHook(() => useAssessmentIntake())
      await waitFor(() => {
        expect(result.current.loading).toBe(false)
      })
      expect(result.current.data).toBe(null)
      expect(result.current.error).toBe(null)
      expect(mockFetchAssessmentIntake).not.toHaveBeenCalled()
    } finally {
      mockAuthState.user = original
    }
  })

  it('retries fetch when refresh is called multiple times', async () => {
    mockFetchAssessmentIntake.mockResolvedValue(mockData)
    const { result } = renderHook(() => useAssessmentIntake())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    for (let i = 0; i < 3; i++) {
      await act(async () => {
        result.current.refresh()
      })
    }

    await waitFor(() => {
      expect(mockFetchAssessmentIntake).toHaveBeenCalledTimes(4)
    })
  })

  it('passes abort signal to fetch function', async () => {
    mockFetchAssessmentIntake.mockResolvedValue(mockData)
    const { result } = renderHook(() => useAssessmentIntake())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(mockFetchAssessmentIntake).toHaveBeenCalledWith(
      expect.any(AbortSignal),
    )
  })
})
