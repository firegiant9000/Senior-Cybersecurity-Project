import { API_BASE_URL, fetchWithAuth, getJsonAuth } from "./fetchWithAuth";

export interface SourceFreshness {
  source: string
  last_run_at: string | null
  last_successful_run_at: string | null
  consecutive_failures: number
  status: string | null
  records_ingested: number | null
  total_records: number | null
  error_message: string | null
  trigger: string | null
  retry_count: number
  skipped_reason: string | null
}

export interface FreshnessResponse {
  sources: SourceFreshness[]
}

export async function fetchIngestFreshness(signal: AbortSignal): Promise<FreshnessResponse> {
  return getJsonAuth<FreshnessResponse>(
    `${API_BASE_URL}/api/v1/ingest/freshness`,
    signal
  )
}

export interface IngestRunItem {
  id: string
  source: string
  started_at: string | null
  finished_at: string | null
  status: string
  records_ingested: number
  error_message: string | null
  trigger: string
  retry_count: number
  skipped_reason: string | null
  next_scheduled_at: string | null
}

export interface IngestRunsResponse {
  items: IngestRunItem[]
  total: number
  page: number
  page_size: number
}

export interface TriggerIngestResponse {
  message: string
  source?: string
}

export async function triggerIngestion(signal: AbortSignal, source?: string): Promise<TriggerIngestResponse> {
  const body = source ? JSON.stringify({ source }) : undefined
  const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/ingest/trigger`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
    signal,
  })
  if (!response.ok) {
    const text = await response.text().catch(() => response.statusText)
    throw new Error(`Trigger failed: ${text}`)
  }
  return response.json() as Promise<TriggerIngestResponse>
}

export async function fetchIngestRuns(
  signal: AbortSignal,
  page = 1,
  pageSize = 20,
  source?: string,
  status?: string,
): Promise<IngestRunsResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (source) params.set('source', source)
  if (status) params.set('status', status)
  const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/ingest/runs?${params}`, { signal })
  if (!response.ok) throw new Error(`Ingest runs request failed: ${response.statusText}`)
  return response.json() as Promise<IngestRunsResponse>
}

export interface RetryRunResponse {
  source: string
  status: string
  message: string
}

export async function retryIngestRun(runId: string): Promise<RetryRunResponse> {
  const response = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/ingest/runs/${runId}/retry`,
    { method: 'POST' },
  )
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(body.detail ?? `Retry failed: ${response.statusText}`)
  }
  return response.json() as Promise<RetryRunResponse>
}

export interface CancelRunResponse {
  cancelled: boolean
  warning: string | null
}

export async function cancelIngestRun(runId: string): Promise<CancelRunResponse> {
  const response = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/ingest/runs/${runId}/cancel`,
    { method: 'POST' },
  )
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string }
    throw new Error(body.detail ?? `Cancel failed: ${response.statusText}`)
  }
  return response.json() as Promise<CancelRunResponse>
}
