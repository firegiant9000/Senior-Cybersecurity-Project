import { useState, useEffect, useCallback } from 'react'
import {
  fetchNvdTimeline,
  fetchRecentKev,
  type NvdTimelinePoint,
  type KevEntry,
} from '../api/tabsApi'
import { fetchSeverityDistribution, type SeverityCount } from '../api/dashboardSummary'

export interface ThreatIntelData {
  nvdTimeline: NvdTimelinePoint[]
  severityDistribution: SeverityCount[]
  recentKev: KevEntry[]
}

export interface UseThreatIntelResult {
  data: ThreatIntelData
  loading: boolean
  errors: string[]
  refresh: () => void
}

const EMPTY: ThreatIntelData = { nvdTimeline: [], severityDistribution: [], recentKev: [] }

function settled<T>(p: Promise<T>): Promise<PromiseSettledResult<T>> {
  return p.then(
    (value) => ({ status: 'fulfilled' as const, value }),
    (reason: unknown) => ({ status: 'rejected' as const, reason }),
  )
}

export function useThreatIntelData(): UseThreatIntelResult {
  const [data, setData] = useState<ThreatIntelData>(EMPTY)
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
      settled(fetchNvdTimeline(signal)),
      settled(fetchSeverityDistribution(signal)),
      settled(fetchRecentKev(signal, 50)),
    ]).then(([timelineR, severityR, kevR]) => {
      const errs: string[] = []
      const warn = (r: PromiseSettledResult<unknown>, label: string) => {
        if (r.status === 'rejected') {
          const msg = r.reason instanceof Error ? r.reason.message : String(r.reason)
          errs.push(`${label}: ${msg}`)
        }
      }
      warn(timelineR, 'CVE timeline')
      warn(severityR, 'Severity distribution')
      warn(kevR, 'Recent KEV')

      setData({
        nvdTimeline: timelineR.status === 'fulfilled' ? timelineR.value.items : [],
        severityDistribution: severityR.status === 'fulfilled' ? severityR.value.items : [],
        recentKev: kevR.status === 'fulfilled' ? kevR.value.items : [],
      })
      setErrors(errs)
    }).finally(() => setLoading(false))

    return () => controller.abort()
  }, [refreshKey])

  return { data, loading, errors, refresh }
}
