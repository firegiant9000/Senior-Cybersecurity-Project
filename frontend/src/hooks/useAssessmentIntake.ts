import { useState, useEffect, useCallback } from 'react'
import { fetchAssessmentIntake, type AssessmentIntakeResponse } from '../api/assessmentIntake'
import { useAuth } from '../context/AuthContext'

export interface UseAssessmentIntakeResult {
  data: AssessmentIntakeResponse | null
  loading: boolean
  error: string | null
  refresh: () => void
}

export function useAssessmentIntake(): UseAssessmentIntakeResult {
  const { user } = useAuth()
  const [data, setData] = useState<AssessmentIntakeResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  const refresh = useCallback(() => setRefreshKey(k => k + 1), [])

  useEffect(() => {
    if (!user) {
      setData(null)
      setError(null)
      setLoading(false)
      return
    }
    const ac = new AbortController()
    setLoading(true)
    setError(null)
    fetchAssessmentIntake(ac.signal)
      .then(d => { if (!ac.signal.aborted) setData(d) })
      .catch((err) => {
        if (!ac.signal.aborted) {
          setData(null)
          setError(err instanceof Error ? err.message : 'Failed to load assessment intake')
        }
      })
      .finally(() => { if (!ac.signal.aborted) setLoading(false) })
    return () => ac.abort()
  }, [user, refreshKey])

  return { data, loading, error, refresh }
}
