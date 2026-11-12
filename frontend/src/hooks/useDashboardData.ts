/**
 * Data-fetching hook for the fixed Overview.
 *
 * Fetches only what the Overview shows: severity distribution, KEV total,
 * loss projection and risk score stats. `loadingHeavy` is kept for the
 * consumer API and always equals `loading`.
 */

import { useState, useEffect, useCallback, useRef } from 'react'
import { useAuth } from '../context/AuthContext'
import {
  fetchSeverityDistribution,
  type SeverityCount,
} from '../api/dashboardSummary'
import {
  fetchKevTotal,
  fetchRiskScoreStats,
  type RiskScoreStatsResponse,
} from '../api/tabsApi'
import {
  fetchLossProjection,
  type LossProjection,
} from '../api/lossProjection'

export interface DashboardData {
  lossProjection:       LossProjection | null
  severityDistribution: SeverityCount[]
  kevTotal:             number
  riskScoreStats:       RiskScoreStatsResponse | null
}

export interface UseDashboardDataResult {
  data:         DashboardData
  loading:      boolean
  loadingHeavy: boolean
  errors:       string[]
  lastUpdated:  Date | null
  refresh:      () => void
  setOnProgress?: (callback: (itemName: string) => void) => void
}

const EMPTY_DATA: DashboardData = {
  lossProjection:       null,
  severityDistribution: [],
  kevTotal:             0,
  riskScoreStats:       null,
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
  const [errors,       setErrors]       = useState<string[]>([])
  const [lastUpdated,  setLastUpdated]  = useState<Date | null>(null)
  const [refreshKey,   setRefreshKey]   = useState(0)
  const onProgressRef = useRef<((itemName: string) => void) | undefined>()

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  const setOnProgress = useCallback((callback: (itemName: string) => void) => {
    onProgressRef.current = callback
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller

    setLoading(true)
    setErrors([])

    const t = <T>(p: Promise<T>, label: string) =>
      settled(withTimeout(p, TIMEOUT_MS, label))

    const trackProgress = (label: string) => {
      onProgressRef.current?.(label)
    }

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

    Promise.all([
      t(fetchSeverityDistribution(signal), 'Severity distribution').then(r => { trackProgress('Severity distribution'); return r; }),
      t(fetchKevTotal(signal),             'KEV total').then(r => { trackProgress('KEV total'); return r; }),
      t(fetchLossProjection(signal),       'Loss projection').then(r => { trackProgress('Loss projection'); return r; }),
      t(fetchRiskScoreStats(signal),       'Risk score stats').then(r => { trackProgress('Risk score stats'); return r; }),
    ]).then(([severityR, kevR, lossR, riskR]) => {
      if (signal.aborted) return

      type LossProjectionResult = PromiseSettledResult<LossProjection>
      type SeverityResult       = PromiseSettledResult<{ items: SeverityCount[] }>
      type KevTotalResult       = PromiseSettledResult<number>
      type RiskStatsResult      = PromiseSettledResult<RiskScoreStatsResponse>

      const errs = collectErrors(
        [severityR, kevR, lossR, riskR],
        ['Severity data', 'KEV total', 'Loss projection', 'Risk score stats'],
      )

      setData({
        lossProjection:       extract(lossR     as LossProjectionResult, null),
        severityDistribution: extract(severityR as SeverityResult,       { items: [] }).items,
        kevTotal:             extract(kevR      as KevTotalResult,       0),
        riskScoreStats:       extract(riskR     as RiskStatsResult,      null),
      })
      setErrors(errs)
      setLastUpdated(new Date())
      setLoading(false)
    }).catch(() => {
      // Catastrophic failure (e.g. AbortError from cleanup) — don't surface
      if (!signal.aborted) setLoading(false)
    })

    return () => controller.abort()
  }, [refreshKey, user?.uid])

  return { data, loading, loadingHeavy: loading, errors, lastUpdated, refresh, setOnProgress }
}
