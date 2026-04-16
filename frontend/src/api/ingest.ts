import { API_BASE_URL, fetchWithAuth, getJsonAuth } from "./fetchWithAuth";

export interface SourceFreshness {
  source: string
  last_run_at: string | null  // ISO datetime
  status: string | null
  records_ingested: number | null
  total_records: number | null
  error_message: string | null
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
