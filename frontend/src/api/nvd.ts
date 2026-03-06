/**
 * NVD (National Vulnerability Database) API client.
 */

const API_BASE_URL =
  (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
    .VITE_API_BASE_URL || 'http://localhost:8000'

// ─── Types ───────────────────────────────────────────────────────────────────

export type SortBy = 'id' | 'published_date' | 'last_modified' | 'cvss_score'

export type SortOrder = 'asc' | 'desc'

export interface NvdCveItem {
  id: string
  cve_id: string
  description: string | null
  published_date: string | null
  last_modified: string | null
  cvss_score: number | null
  cvss_vector: string | null
}

export interface NvdCveListResponse {
  total: number
  page: number
  page_size: number
  items: NvdCveItem[]
}

// ─── API call ─────────────────────────────────────────────────────────────────

interface FetchParams {
  page?: number
  pageSize?: number
  sortBy?: SortBy
  sortOrder?: SortOrder
}

export async function fetchNvdCves({
  page = 1,
  pageSize = 50,
  sortBy = 'published_date',
  sortOrder = 'desc',
}: FetchParams = {}): Promise<NvdCveListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_by: sortBy,
    sort_order: sortOrder,
  })

  const response = await fetch(
    `${API_BASE_URL}/api/v1/nvd/cves?${params}`
  )

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to fetch NVD CVEs: ${response.statusText}`
    )
  }

  return response.json() as Promise<NvdCveListResponse>
}
