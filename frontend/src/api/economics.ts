/**
 * Economics API client (Census economic indicators).
 */

const API_BASE_URL =
  (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
    .VITE_API_BASE_URL || `${window.location.protocol}//${window.location.hostname}:8000`

// ─── Types ───────────────────────────────────────────────────────────────────

export type SortBy = 'id' | 'state' | 'median_income' | 'unemployment_rate' | 'poverty_rate'

export type SortOrder = 'asc' | 'desc'

export interface EconomicIndicatorItem {
  id: string
  state: string
  median_income: number | null
  unemployment_rate: number | null
  poverty_rate: number | null
  population: number | null
}

export interface EconomicIndicatorListResponse {
  total: number
  page: number
  page_size: number
  items: EconomicIndicatorItem[]
}

// ─── API call ─────────────────────────────────────────────────────────────────

interface FetchParams {
  page?: number
  pageSize?: number
  sortBy?: SortBy
  sortOrder?: SortOrder
}

export async function fetchEconomicIndicators({
  page = 1,
  pageSize = 50,
  sortBy = 'state',
  sortOrder = 'asc',
}: FetchParams = {}): Promise<EconomicIndicatorListResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    sort_by: sortBy,
    sort_order: sortOrder,
  })

  const response = await fetch(
    `${API_BASE_URL}/api/v1/economics/indicators?${params}`
  )

  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(
      (body as { detail?: string }).detail ??
        `Failed to fetch economic indicators: ${response.statusText}`
    )
  }

  return response.json() as Promise<EconomicIndicatorListResponse>
}
