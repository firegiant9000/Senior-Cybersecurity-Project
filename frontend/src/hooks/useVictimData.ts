import { useState, useEffect, useCallback } from 'react'
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
  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    setLoading(true)
    setErrors([])

    Promise.all([
      settled(fetchAttackTypes(signal)),
      settled(fetchIndustryRisk(signal)),
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

  return { data, loading, errors, refresh }
}
