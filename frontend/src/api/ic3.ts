/**
 * IC3 (FBI Internet Crime Complaint Center) API client.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

// ─── Types ───────────────────────────────────────────────────────────────────

export type SortBy = 'id' | 'year' | 'complaint_count' | 'loss_amount'

export type SortOrder = 'asc' | 'desc'

export interface IC3IncidentItem {
  id: string
  year: number
  category: string | null
  complaint_count: number | null
  loss_amount: number | null
}

export interface IC3IncidentListResponse {
  total: number
  page: number
  page_size: number
  items: IC3IncidentItem[]
}

// ─── API call ─────────────────────────────────────────────────────────────────

interface FetchParams {
  page?: number
  pageSize?: number
  sortBy?: SortBy
  sortOrder?: SortOrder
}

export async function fetchIC3Incidents({
  page = 1,
  pageSize = 50,
  sortBy = 'year',
  sortOrder = 'desc',
}: FetchParams = {}): Promise<IC3IncidentListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_by: sortBy,
    sort_order: sortOrder,
  })

  const response = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/ic3/incidents?${params}`
  )

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to fetch IC3 incidents: ${response.statusText}`
    )
  }

  return response.json() as Promise<IC3IncidentListResponse>
}
