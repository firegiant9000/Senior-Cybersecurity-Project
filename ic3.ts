/**
 * IC3 (FBI Internet Crime Complaint Center) API client.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

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

  return getJsonAuth<IC3IncidentListResponse>(
    `${API_BASE_URL}/api/v1/ic3/incidents?${params}`
  )
}
