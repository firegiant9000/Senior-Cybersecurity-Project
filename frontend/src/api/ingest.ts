const API_BASE_URL =
  (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
    .VITE_API_BASE_URL || `http://${window.location.hostname}:8000`

export interface SourceFreshness {
  source: string
  last_run_at: string | null  // ISO datetime
  status: string | null
  records_ingested: number | null
  error_message: string | null
}

export interface FreshnessResponse {
  sources: SourceFreshness[]
}

export async function fetchIngestFreshness(signal: AbortSignal): Promise<FreshnessResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/ingest/freshness`, { signal })
  if (!response.ok) throw new Error(`Freshness request failed: ${response.statusText}`)
  return response.json() as Promise<FreshnessResponse>
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
  const response = await fetch(`${API_BASE_URL}/api/v1/ingest/runs?${params}`, { signal })
  if (!response.ok) throw new Error(`Ingest runs request failed: ${response.statusText}`)
  return response.json() as Promise<IngestRunsResponse>
}
