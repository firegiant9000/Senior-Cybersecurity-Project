import { renderHook, waitFor } from '@testing-library/react'
import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockAuthState: { user: { uid: string; email: string } | null } = {
  user: { uid: 'u1', email: 'test@example.com' },
}
vi.mock('../../context/AuthContext', () => ({
  useAuth: vi.fn(() => mockAuthState),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}))

const fetchSeverityDistribution = vi.fn()
const fetchDashboardSummary = vi.fn()
const fetchAttackTypes = vi.fn()
const fetchIndustryRisk = vi.fn()
const fetchGeographicHeatmap = vi.fn()
const fetchSectorAttackMatrix = vi.fn()
vi.mock('../../api/dashboardSummary', () => ({
  fetchSeverityDistribution: (...a: unknown[]) => fetchSeverityDistribution(...a),
  fetchDashboardSummary: (...a: unknown[]) => fetchDashboardSummary(...a),
  fetchAttackTypes: (...a: unknown[]) => fetchAttackTypes(...a),
  fetchIndustryRisk: (...a: unknown[]) => fetchIndustryRisk(...a),
  fetchGeographicHeatmap: (...a: unknown[]) => fetchGeographicHeatmap(...a),
  fetchSectorAttackMatrix: (...a: unknown[]) => fetchSectorAttackMatrix(...a),
}))

const fetchKevTotal = vi.fn()
const fetchRiskScoreStats = vi.fn()
const fetchTemporalTrends = vi.fn()
const fetchIC3AnomalyCount = vi.fn()
const fetchEscalatingSectorCount = vi.fn()
vi.mock('../../api/tabsApi', () => ({
  fetchKevTotal: (...a: unknown[]) => fetchKevTotal(...a),
  fetchRiskScoreStats: (...a: unknown[]) => fetchRiskScoreStats(...a),
  fetchTemporalTrends: (...a: unknown[]) => fetchTemporalTrends(...a),
  fetchIC3AnomalyCount: (...a: unknown[]) => fetchIC3AnomalyCount(...a),
  fetchEscalatingSectorCount: (...a: unknown[]) => fetchEscalatingSectorCount(...a),
}))

const fetchExecutiveSummary = vi.fn()
vi.mock('../../api/executiveSummary', () => ({
  fetchExecutiveSummary: (...a: unknown[]) => fetchExecutiveSummary(...a),
}))

const fetchLossProjection = vi.fn()
vi.mock('../../api/lossProjection', () => ({
  fetchLossProjection: (...a: unknown[]) => fetchLossProjection(...a),
}))

import { useDashboardData } from '../useDashboardData'

describe('useDashboardData', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    fetchSeverityDistribution.mockResolvedValue({ items: [{ severity: 'HIGH', count: 3 }] })
    fetchKevTotal.mockResolvedValue(7)
    fetchLossProjection.mockResolvedValue({ total: 1 })
    fetchRiskScoreStats.mockResolvedValue({ avg_risk: 42, top_vendors: [] })
  })

  it('fetches only the four datasets the fixed Overview shows', async () => {
    const { result } = renderHook(() => useDashboardData())
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(fetchSeverityDistribution).toHaveBeenCalledTimes(1)
    expect(fetchKevTotal).toHaveBeenCalledTimes(1)
    expect(fetchLossProjection).toHaveBeenCalledTimes(1)
    expect(fetchRiskScoreStats).toHaveBeenCalledTimes(1)

    for (const unused of [
      fetchExecutiveSummary,
      fetchGeographicHeatmap,
      fetchSectorAttackMatrix,
      fetchIndustryRisk,
      fetchAttackTypes,
      fetchTemporalTrends,
      fetchDashboardSummary,
      fetchIC3AnomalyCount,
      fetchEscalatingSectorCount,
    ]) {
      expect(unused).not.toHaveBeenCalled()
    }
  })

  it('returns the four fields and keeps loadingHeavy equal to loading', async () => {
    const { result } = renderHook(() => useDashboardData())
    expect(result.current.loadingHeavy).toBe(result.current.loading)
    await waitFor(() => expect(result.current.loading).toBe(false))

    expect(result.current.loadingHeavy).toBe(false)
    expect(Object.keys(result.current.data).sort()).toEqual(
      ['kevTotal', 'lossProjection', 'riskScoreStats', 'severityDistribution'],
    )
    expect(result.current.data.kevTotal).toBe(7)
    expect(result.current.errors).toEqual([])
  })
})
