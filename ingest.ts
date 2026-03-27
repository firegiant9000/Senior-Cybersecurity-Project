import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

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

export async function fetchIngestFreshness(): Promise<FreshnessResponse> {
  return getJsonAuth<FreshnessResponse>(
    `${API_BASE_URL}/api/v1/ingest/freshness`
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

export async function fetchIngestRuns(
  page = 1,
  pageSize = 20,
  source?: string,
  status?: string,
): Promise<IngestRunsResponse> {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) })
  if (source) params.set('source', source)
  if (status) params.set('status', status)
  return getJsonAuth<IngestRunsResponse>(`${API_BASE_URL}/api/v1/ingest/runs?${params}`)
}
