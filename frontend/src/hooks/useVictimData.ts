import { useState, useEffect, useCallback, useRef } from 'react'
import { fetchAttackTypes, fetchIndustryRisk, type AttackTypeStats, type IndustryRiskProfile } from '../api/dashboardSummary'

export interface VictimData {
  attackTypes: AttackTypeStats[]
  industryRisk: IndustryRiskProfile[]
}

export interface UseVictimResult {
  data: VictimData
  loading: boolean
  errors: string[]
  refresh: () => void
  setOnProgress?: (callback: (itemName: string) => void) => void
}

function settled<T>(p: Promise<T>): Promise<PromiseSettledResult<T>> {
  return p.then(
    (value) => ({ status: 'fulfilled' as const, value }),
    (reason: unknown) => ({ status: 'rejected' as const, reason }),
  )
}

export function useVictimData(): UseVictimResult {
  const [data, setData] = useState<VictimData>({ attackTypes: [], industryRisk: [] })
  const [loading, setLoading] = useState(true)
  const [errors, setErrors] = useState<string[]>([])
  const [refreshKey, setRefreshKey] = useState(0)
  const onProgressRef = useRef<((itemName: string) => void) | undefined>()

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  const setOnProgress = useCallback((callback: (itemName: string) => void) => {
    onProgressRef.current = callback
  }, [])

  const trackProgress = (label: string) => {
    onProgressRef.current?.(label)
  }

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    setLoading(true)
    setErrors([])

    Promise.all([
      settled(fetchAttackTypes(signal)).then(r => { trackProgress('Attack types'); return r; }),
      settled(fetchIndustryRisk(signal)).then(r => { trackProgress('Industry risk'); return r; }),
    ]).then(([attackR, industryR]) => {
      if (signal.aborted) return
      const errs: string[] = []
      const warn = (r: PromiseSettledResult<unknown>, label: string) => {
        if (r.status === 'rejected') {
          const err = r.reason
          if (err instanceof Error && err.name === 'AbortError') return
          const msg = err instanceof Error ? err.message : String(err)
          errs.push(`${label}: ${msg}`)
        }
      }
      warn(attackR, 'Attack types')
      warn(industryR, 'Industry risk')

      setData({
        attackTypes: attackR.status === 'fulfilled' ? attackR.value.items : [],
        industryRisk: industryR.status === 'fulfilled' ? industryR.value.items : [],
      })
      setErrors(errs)
    }).finally(() => { if (!signal.aborted) setLoading(false) })

    return () => controller.abort()
  }, [refreshKey])

  return { data, loading, errors, refresh, setOnProgress }
}
