import { useState, useEffect, useCallback } from 'react'
import { fetchAssessmentReadiness, type AssessmentReadiness } from '../api/assessmentReadiness'
import { useAuth } from '../context/AuthContext'

export interface UseAssessmentReadinessResult {
  data: AssessmentReadiness | null
  loading: boolean
  refresh: () => void
}

export function useAssessmentReadiness(): UseAssessmentReadinessResult {
  const { user } = useAuth()
  const [data, setData] = useState<AssessmentReadiness | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshKey, setRefreshKey] = useState(0)

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  useEffect(() => {
    if (!user) {
      setData(null)
      setLoading(false)
      return
    }
    const ac = new AbortController()
    setLoading(true)
    fetchAssessmentReadiness(ac.signal)
      .then(d => { if (!ac.signal.aborted) setData(d) })
      .catch(() => { if (!ac.signal.aborted) setData(null) })
      .finally(() => { if (!ac.signal.aborted) setLoading(false) })
    return () => ac.abort()
  }, [user, refreshKey])

  return { data, loading, refresh }
}
