import { useState, useEffect, useCallback } from 'react'
import { fetchRecentKev, fetchRecentNvdCves, type KevEntry, type NvdCveItem } from '../api/tabsApi'

export interface AlertsData {
  recentKev: KevEntry[]
  recentCves: NvdCveItem[]
}

export interface UseAlertsResult {
  data: AlertsData
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

export function useAlertsData(): UseAlertsResult {
  const [data, setData] = useState<AlertsData>({ recentKev: [], recentCves: [] })
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
      settled(fetchRecentKev(signal, 20)),
      settled(fetchRecentNvdCves(signal, 20)),
    ]).then(([kevR, cveR]) => {
      const errs: string[] = []
      const warn = (r: PromiseSettledResult<unknown>, label: string) => {
        if (r.status === 'rejected') {
          const err = r.reason
          if (err instanceof Error && err.name === 'AbortError') return
          const msg = err instanceof Error ? err.message : String(err)
          errs.push(`${label}: ${msg}`)
        }
      }
      warn(kevR, 'KEV alerts')
      warn(cveR, 'Recent CVEs')

      setData({
        recentKev: kevR.status === 'fulfilled' ? kevR.value.items : [],
        recentCves: cveR.status === 'fulfilled' ? cveR.value.items : [],
      })
      setErrors(errs)
    }).finally(() => setLoading(false))

    return () => controller.abort()
  }, [refreshKey])

  return { data, loading, errors, refresh }
}
