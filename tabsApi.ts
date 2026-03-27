/**
 * API client functions for the four analytic tabs:
 * Threat Intelligence, Trends, Alerts Feed, Victim Profile.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

// ─── Threat Intelligence ──────────────────────────────────────────────────────

export interface NvdTimelinePoint {
  year: number
  count: number
}
export interface NvdTimelineResponse {
  items: NvdTimelinePoint[]
}

export interface KevEntry {
  id: string
  vulnerability_name: string
  vendor: string | null
  product: string | null
  severity_label: string
  severity_score: number | null
  risk_score: number | null
  is_kev: boolean
  kev_date_added: string | null
  nvd_published: string | null
  nvd_last_modified: string | null
}
export interface KevListResponse {
  total: number
  page: number
  page_size: number
  items: KevEntry[]
}

export function fetchNvdTimeline(): Promise<NvdTimelineResponse> {
  return getJsonAuth<NvdTimelineResponse>(
    `${API_BASE_URL}/api/v1/nvd/analytics/timeline`
  )
}

export function fetchRecentKev(pageSize = 50): Promise<KevListResponse> {
  return getJsonAuth<KevListResponse>(
    `${API_BASE_URL}/api/v1/vulnerabilities/exploited?sort_by=kev_date_added&sort_order=desc&page_size=${pageSize}`
  )
}

// ─── Trends ───────────────────────────────────────────────────────────────────

export interface TemporalTrend {
  year: number
  complaint_count: number
  total_loss: number
  avg_loss_per_incident: number
}
export interface TemporalTrendResponse {
  items: TemporalTrend[]
  attack_type: string | null
}

export function fetchTemporalTrends(
  attackType?: string,
  yearFrom?: number,
  yearTo?: number,
): Promise<TemporalTrendResponse> {
  const p = new URLSearchParams()
  if (attackType) p.set('attack_type', attackType)
  if (yearFrom !== undefined) p.set('year_from', String(yearFrom))
  if (yearTo !== undefined) p.set('year_to', String(yearTo))
  const qs = p.toString() ? `?${p.toString()}` : ''
  return getJsonAuth<TemporalTrendResponse>(
    `${API_BASE_URL}/api/v1/ic3/analytics/temporal-trends${qs}`
  )
}

export function fetchAttackTypeOptions(): Promise<{ attack_types: string[] }> {
  return getJsonAuth<{ attack_types: string[]; states: string[]; years: number[] }>(
    `${API_BASE_URL}/api/v1/ic3/filter-options`
  )
}

/** Fetch just the total count of KEV entries (lightweight — page_size=1). */
export async function fetchKevTotal(): Promise<number> {
  return getJsonAuth<{ total: number }>(
    `${API_BASE_URL}/api/v1/vulnerabilities/exploited?page_size=1`
  ).then((r) => r.total)
}

// ─── Alerts Feed ──────────────────────────────────────────────────────────────

export interface NvdCveItem {
  id: string
  description: string
  severity_label: string
  severity_score: number | null
  published_date: string | null
  last_modified: string | null
}
export interface NvdCveListResponse {
  total: number
  page: number
  page_size: number
  items: NvdCveItem[]
}

export function fetchRecentNvdCves(pageSize = 20): Promise<NvdCveListResponse> {
  return getJsonAuth<NvdCveListResponse>(
    `${API_BASE_URL}/api/v1/nvd/cves?sort_by=published_date&sort_order=desc&page_size=${pageSize}`
  )
}
