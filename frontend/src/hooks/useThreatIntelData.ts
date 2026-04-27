import { useState, useEffect, useCallback, useRef } from 'react'
import {
  fetchNvdTimeline,
  fetchRecentKev,
  fetchRecentNvdCves,
  type NvdTimelinePoint,
  type KevEntry,
  type NvdCveItem,
} from '../api/tabsApi'
import { fetchSeverityDistribution, type SeverityCount } from '../api/dashboardSummary'

export interface ThreatIntelData {
  nvdTimeline: NvdTimelinePoint[]
  severityDistribution: SeverityCount[]
  recentKev: KevEntry[]
  recentCves: NvdCveItem[]
}

export interface UseThreatIntelResult {
  data: ThreatIntelData
  loading: boolean
  errors: string[]
  refresh: () => void
  setOnProgress?: (callback: (itemName: string) => void) => void
}

const EMPTY: ThreatIntelData = { nvdTimeline: [], severityDistribution: [], recentKev: [], recentCves: [] }

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
      settled(fetchNvdTimeline(signal)).then(r => { trackProgress('CVE timeline'); return r; }),
      settled(fetchSeverityDistribution(signal)).then(r => { trackProgress('Severity distribution'); return r; }),
      settled(fetchRecentKev(signal, 50)).then(r => { trackProgress('Recent KEV'); return r; }),
      settled(fetchRecentNvdCves(signal, 20)).then(r => { trackProgress('Recent CVEs'); return r; }),
    ]).then(([timelineR, severityR, kevR, cveR]) => {
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
      warn(timelineR, 'CVE timeline')
      warn(severityR, 'Severity distribution')
      warn(kevR, 'Recent KEV')
      warn(cveR, 'Recent CVEs')

      setData({
        nvdTimeline: timelineR.status === 'fulfilled' ? timelineR.value.items : [],
        severityDistribution: severityR.status === 'fulfilled' ? severityR.value.items : [],
        recentKev: kevR.status === 'fulfilled' ? kevR.value.items : [],
        recentCves: cveR.status === 'fulfilled' ? cveR.value.items : [],
      })
      setErrors(errs)
    }).finally(() => { if (!signal.aborted) setLoading(false) })

    return () => controller.abort()
  }, [refreshKey])

  return { data, loading, errors, refresh, setOnProgress }
}
