import { useState, useEffect, useCallback } from 'react'
import { fetchTemporalTrends, fetchAttackTypeOptions, type TemporalTrend } from '../api/tabsApi'

export interface TrendsData {
  trends: TemporalTrend[]
  attackTypeOptions: string[]
  selectedAttackType: string | undefined
  selectedSector: string | undefined
  yearFrom: number | undefined
  yearTo: number | undefined
}

export interface UseTrendsResult {
  data: TrendsData
  loading: boolean
  errors: string[]
  setAttackType: (v: string | undefined) => void
  setSector: (v: string | undefined) => void
  setYearFrom: (v: number | undefined) => void
  setYearTo: (v: number | undefined) => void
  refresh: () => void
}

function settled<T>(p: Promise<T>): Promise<PromiseSettledResult<T>> {
  return p.then(
    (value) => ({ status: 'fulfilled' as const, value }),
    (reason: unknown) => ({ status: 'rejected' as const, reason }),
  )
}

export function useTrendsData(): UseTrendsResult {
  const [trends, setTrends] = useState<TemporalTrend[]>([])
  const [attackTypeOptions, setAttackTypeOptions] = useState<string[]>([])
  const [selectedAttackType, setSelectedAttackType] = useState<string | undefined>(undefined)
  const [selectedSector, setSelectedSector] = useState<string | undefined>(undefined)
  const [yearFrom, setYearFrom] = useState<number | undefined>(undefined)
  const [yearTo, setYearTo] = useState<number | undefined>(undefined)
  const [loading, setLoading] = useState(true)
  const [errors, setErrors] = useState<string[]>([])
  const [refreshKey, setRefreshKey] = useState(0)
  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  // Load filter options once
  useEffect(() => {
    const controller = new AbortController()
    fetchAttackTypeOptions(controller.signal)
      .then(r => setAttackTypeOptions(r.attack_types ?? []))
      .catch(() => { /* non-fatal */ })
    return () => controller.abort()
  }, [])

  // Re-fetch trends when filters or refreshKey change
  useEffect(() => {
    const controller = new AbortController()
    setLoading(true)
    setErrors([])

    settled(fetchTemporalTrends(controller.signal, selectedAttackType, selectedSector, yearFrom, yearTo))
      .then(r => {
        if (r.status === 'fulfilled') {
          setTrends(r.value.items)
        } else {
          const err = r.reason
          if (err instanceof Error && err.name === 'AbortError') return
          const msg = err instanceof Error ? err.message : String(err)
          setErrors([`Trends: ${msg}`])
          setTrends([])
        }
      })
      .finally(() => setLoading(false))

    return () => controller.abort()
  }, [selectedAttackType, selectedSector, yearFrom, yearTo, refreshKey])

  return {
    data: { trends, attackTypeOptions, selectedAttackType, selectedSector, yearFrom, yearTo },
    loading,
    errors,
    setAttackType: setSelectedAttackType,
    setSector: setSelectedSector,
    setYearFrom,
    setYearTo,
    refresh,
  }
}
