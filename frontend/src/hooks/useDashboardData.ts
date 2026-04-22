/**
 * Central data-fetching hook for the Overview dashboard.
 *
 * Two-wave loading strategy:
 *   Wave 1 (fast) — drives stat cards and quick charts above the fold:
 *     summary, attackTypes, severityDistribution, temporalTrends, kevTotal
 *   Wave 2 (heavy) — background-loads large dataset widgets:
 *     geographicThreats, sectorAttackMatrix, industryRisk
 *
 * `loading` is true only during wave 1.
 * `loadingHeavy` is true during wave 2 (wave 1 already resolved).
 */

import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../context/AuthContext'
import {
  fetchDashboardSummary,
  fetchAttackTypes,
  fetchIndustryRisk,
  fetchGeographicHeatmap,
  fetchSeverityDistribution,
  fetchSectorAttackMatrix,
  type DashboardSummary,
  type AttackTypeStats,
  type IndustryRiskProfile,
  type GeographicThreat,
  type SeverityCount,
  type SectorAttackCombination,
} from '../api/dashboardSummary'
import {
  fetchTemporalTrends,
  fetchKevTotal,
  fetchRiskScoreStats,
  fetchIC3AnomalyCount,
  fetchEscalatingSectorCount,
  type TemporalTrend,
  type RiskScoreStatsResponse,
} from '../api/tabsApi'
import {
  fetchExecutiveSummary,
  type ExecutiveSummary,
} from '../api/executiveSummary'
import {
  fetchLossProjection,
  type LossProjection,
} from '../api/lossProjection'

export interface DashboardData {
  summary:              DashboardSummary | null
  executiveSummary:     ExecutiveSummary | null
  lossProjection:       LossProjection | null
  attackTypes:          AttackTypeStats[]
  industryRisk:         IndustryRiskProfile[]
  geographicThreats:    GeographicThreat[]
  severityDistribution: SeverityCount[]
  sectorAttackMatrix:   SectorAttackCombination[]
  temporalTrends:       TemporalTrend[]
  kevTotal:             number
  riskScoreStats:       RiskScoreStatsResponse | null
  ic3AnomalyCount:      number | null
  escalatingSectorCount: number | null
}

export interface UseDashboardDataResult {
  data:         DashboardData
  loading:      boolean
  loadingHeavy: boolean
  errors:       string[]
  lastUpdated:  Date | null
  refresh:      () => void
}

const EMPTY_DATA: DashboardData = {
  summary:              null,
  executiveSummary:     null,
  lossProjection:       null,
  attackTypes:          [],
  industryRisk:         [],
  geographicThreats:    [],
  severityDistribution: [],
  sectorAttackMatrix:   [],
  temporalTrends:       [],
  kevTotal:             0,
  riskScoreStats:       null,
  ic3AnomalyCount:      null,
  escalatingSectorCount: null,
}

const TIMEOUT_MS = 10_000

function withTimeout<T>(promise: Promise<T>, ms: number, label: string): Promise<T> {
  let timerId: ReturnType<typeof setTimeout> | undefined
  const timeout = new Promise<T>((_, reject) => {
    timerId = setTimeout(() => reject(new Error(`${label} timed out after ${ms / 1000}s`)), ms)
  })
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timerId))
}

function settled<T>(p: Promise<T>): Promise<PromiseSettledResult<T>> {
  return p.then(
    (value) => ({ status: 'fulfilled' as const, value }),
    (reason: unknown) => ({ status: 'rejected' as const, reason }),
  )
}

function extract<T>(result: PromiseSettledResult<T>, fallback: T): T {
  return result.status === 'fulfilled' ? result.value : fallback
}

export function useDashboardData(): UseDashboardDataResult {
  const { user } = useAuth()
  const [data,         setData]         = useState<DashboardData>(EMPTY_DATA)
  const [loading,      setLoading]      = useState(true)
  const [loadingHeavy, setLoadingHeavy] = useState(true)
  const [errors,       setErrors]       = useState<string[]>([])
  const [lastUpdated,  setLastUpdated]  = useState<Date | null>(null)
  const [refreshKey,   setRefreshKey]   = useState(0)

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller

    setLoading(true)
    setLoadingHeavy(true)
    setErrors([])

    const t = <T>(p: Promise<T>, label: string) =>
      settled(withTimeout(p, TIMEOUT_MS, label))

    const collectErrors = (results: PromiseSettledResult<unknown>[], labels: string[]): string[] => {
      const errs: string[] = []
      results.forEach((r, i) => {
        if (r.status === 'rejected') {
          const err = r.reason
          if (err instanceof Error && err.name === 'AbortError') return
          const msg = err instanceof Error ? err.message : String(err)
          errs.push(`${labels[i]}: ${msg}`)
        }
      })
      return errs
    }

    // ── Wave 1: fast endpoints that drive the stat cards ─────────────────────
    Promise.all([
      t(fetchDashboardSummary(signal),     'Dashboard summary'),
      t(fetchAttackTypes(signal),          'Attack types'),
      t(fetchSeverityDistribution(signal), 'Severity distribution'),
      t(fetchTemporalTrends(signal),       'Temporal trends'),
      t(fetchKevTotal(signal),             'KEV total'),
      t(fetchExecutiveSummary(signal),     'Executive summary'),
      t(fetchLossProjection(signal),       'Loss projection'),
      t(fetchRiskScoreStats(signal),       'Risk score stats'),
    ]).then(([summaryR, attackR, severityR, trendsR, kevR, execR, lossR, riskR]) => {
      if (signal.aborted) return

      type SummaryResult        = PromiseSettledResult<DashboardSummary>
      type ExecResult           = PromiseSettledResult<ExecutiveSummary>
      type LossProjectionResult = PromiseSettledResult<LossProjection>
      type AttackResult         = PromiseSettledResult<{ items: AttackTypeStats[] }>
      type SeverityResult       = PromiseSettledResult<{ items: SeverityCount[] }>
      type TrendsResult         = PromiseSettledResult<{ items: TemporalTrend[] }>
      type KevTotalResult       = PromiseSettledResult<number>
      type RiskStatsResult      = PromiseSettledResult<RiskScoreStatsResponse>

      const wave1Errors = collectErrors(
        [summaryR, attackR, severityR, trendsR, kevR, execR, lossR, riskR],
        ['Summary', 'Attack types', 'Severity data', 'Temporal trends', 'KEV total', 'Executive summary', 'Loss projection', 'Risk score stats'],
      )

      setData(prev => ({
        ...prev,
        summary:              extract(summaryR  as SummaryResult,        null),
        executiveSummary:     extract(execR     as ExecResult,           null),
        lossProjection:       extract(lossR     as LossProjectionResult, null),
        attackTypes:          extract(attackR   as AttackResult,         { items: [] }).items,
        severityDistribution: extract(severityR as SeverityResult,       { items: [] }).items,
        temporalTrends:       extract(trendsR   as TrendsResult,         { items: [] }).items,
        kevTotal:             extract(kevR      as KevTotalResult,       0),
        riskScoreStats:       extract(riskR     as RiskStatsResult,      null),
      }))
      setErrors(wave1Errors)
      setLastUpdated(new Date())
      setLoading(false)

      // ── Wave 2: heavy endpoints loaded in the background ───────────────────
      Promise.all([
        t(fetchGeographicHeatmap(signal),       'Geographic heatmap'),
        t(fetchSectorAttackMatrix(signal),      'Sector attack matrix'),
        t(fetchIndustryRisk(signal),            'Industry risk'),
        t(fetchIC3AnomalyCount(signal),         'IC3 anomalies'),
        t(fetchEscalatingSectorCount(signal),   'Escalating sectors'),
      ]).then(([geoR, matrixR, industryR, anomalyR, escalatingR]) => {
        if (signal.aborted) return

        type GeoResult        = PromiseSettledResult<{ items: GeographicThreat[] }>
        type MatrixResult     = PromiseSettledResult<{ items: SectorAttackCombination[] }>
        type IndustryResult   = PromiseSettledResult<{ items: IndustryRiskProfile[] }>
        type AnomalyResult    = PromiseSettledResult<number>

        const wave2Errors = collectErrors(
          [geoR, matrixR, industryR, anomalyR, escalatingR],
          ['Geographic data', 'Sector matrix', 'Industry risk', 'IC3 anomalies', 'Escalating sectors'],
        )

        setData(prev => ({
          ...prev,
          geographicThreats:    extract(geoR        as GeoResult,      { items: [] }).items,
          sectorAttackMatrix:   extract(matrixR      as MatrixResult,   { items: [] }).items,
          industryRisk:         extract(industryR    as IndustryResult, { items: [] }).items,
          ic3AnomalyCount:      extract(anomalyR     as AnomalyResult,  null),
          escalatingSectorCount: extract(escalatingR as AnomalyResult,  null),
        }))
        setErrors(prev => [...prev, ...wave2Errors])
      }).finally(() => {
        if (!signal.aborted) setLoadingHeavy(false)
      })
    }).catch(() => {
      // Catastrophic failure (e.g. AbortError from cleanup) — don't surface
      if (!signal.aborted) setLoading(false)
    })

    return () => controller.abort()
  }, [refreshKey, user?.uid])

  return { data, loading, loadingHeavy, errors, lastUpdated, refresh }
}
