/**
 * Exploited vulnerabilities API client.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

// ─── Types ───────────────────────────────────────────────────────────────────

export type SeverityLabel = 'Critical' | 'High' | 'Medium' | 'Low' | 'Unknown'

export type SortBy =
  | 'kev_date_added'
  | 'severity_score'
  | 'risk_score'
  | 'nvd_published'
  | 'id'

export type SortOrder = 'asc' | 'desc'

export interface ExploitedVulnItem {
  id: string
  vulnerability_name: string
  vendor: string | null
  product: string | null
  severity_label: SeverityLabel
  severity_score: number | null
  risk_score: number | null
  is_kev: boolean
  kev_date_added: string | null   // ISO YYYY-MM-DD or null
  nvd_published: string | null    // ISO YYYY-MM-DD or null
  nvd_last_modified: string | null // ISO YYYY-MM-DD or null
}

export interface ExploitedVulnListResponse {
  total: number
  page: number
  page_size: number
  items: ExploitedVulnItem[]
}

// ─── API call ─────────────────────────────────────────────────────────────────

interface FetchParams {
  page?: number
  pageSize?: number
  sortBy?: SortBy
  sortOrder?: SortOrder
}

export async function fetchExploitedVulns({
  page = 1,
  pageSize = 25,
  sortBy = 'kev_date_added',
  sortOrder = 'desc',
}: FetchParams = {}): Promise<ExploitedVulnListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_by: sortBy,
    sort_order: sortOrder,
  })

  return getJsonAuth<ExploitedVulnListResponse>(
    `${API_BASE_URL}/api/v1/vulnerabilities/exploited?${params}`
  )
}
