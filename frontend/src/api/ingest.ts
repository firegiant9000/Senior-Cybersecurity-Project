const API_BASE_URL =
  (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
    .VITE_API_BASE_URL || `http://${window.location.hostname}:8000`

export interface SourceFreshness {
  source: string
  last_run_at: string | null  // ISO datetime
  status: string | null
  records_ingested: number | null
}

export interface FreshnessResponse {
  sources: SourceFreshness[]
}

export async function fetchIngestFreshness(signal: AbortSignal): Promise<FreshnessResponse> {
  const response = await fetch(`${API_BASE_URL}/api/v1/ingest/freshness`, { signal })
  if (!response.ok) throw new Error(`Freshness request failed: ${response.statusText}`)
  return response.json() as Promise<FreshnessResponse>
}
