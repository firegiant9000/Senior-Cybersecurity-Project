/**
 * Dashboard summary API client.
 * Fetches all data needed for the Overview tab widgets.
 */

const API_BASE_URL =
  (import.meta as ImportMeta & { env: Record<string, string | undefined> }).env
    .VITE_API_BASE_URL || `http://${window.location.hostname}:8000`

// ─── Types ───────────────────────────────────────────────────────────────────

export interface DashboardSummary {
  total_complaints: number
  total_losses: number
  avg_loss_per_incident: number
  attack_type_count: number
  sector_count: number
  state_count: number
}

export interface AttackTypeStats {
  attack_type: string
  total_loss: number
  avg_loss: number
  complaint_count: number
}

export interface AttackTypeListResponse {
  items: AttackTypeStats[]
  year: number | null
}

export interface IndustryRiskProfile {
  sector: string
  complaint_count: number
  total_loss: number
  avg_loss_per_incident: number
}

export interface IndustryRiskResponse {
  items: IndustryRiskProfile[]
  year: number | null
}

export interface GeographicThreat {
  state: string
  complaint_count: number
  total_loss: number
  avg_loss_per_incident: number
}

export interface GeographicHeatmapResponse {
  items: GeographicThreat[]
  year: number | null
}

export interface SectorAttackCombination {
  sector: string
  attack_type: string
  complaint_count: number
  total_loss: number
  avg_loss_per_incident: number
}

export interface SectorAttackMatrixResponse {
  items: SectorAttackCombination[]
  year: number | null
}

export interface SeverityCount {
  severity: string
  count: number
}

export interface SeverityDistributionResponse {
  items: SeverityCount[]
  total_cves: number
  date_from: string | null
  date_to: string | null
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

async function getJson<T>(url: string, signal: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal })
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(
      (body as { detail?: string }).detail ??
        `Request failed: ${response.statusText}`
    )
  }
  return response.json() as Promise<T>
}

// ─── API calls ────────────────────────────────────────────────────────────────

export async function fetchDashboardSummary(signal: AbortSignal): Promise<DashboardSummary> {
  return getJson<DashboardSummary>(
    `${API_BASE_URL}/api/v1/ic3/analytics/dashboard-summary`,
    signal
  )
}

export async function fetchAttackTypes(signal: AbortSignal): Promise<AttackTypeListResponse> {
  return getJson<AttackTypeListResponse>(
    `${API_BASE_URL}/api/v1/ic3/analytics/attack-types`,
    signal
  )
}

export async function fetchIndustryRisk(signal: AbortSignal): Promise<IndustryRiskResponse> {
  return getJson<IndustryRiskResponse>(
    `${API_BASE_URL}/api/v1/ic3/analytics/industry-risk`,
    signal
  )
}

export async function fetchGeographicHeatmap(signal: AbortSignal): Promise<GeographicHeatmapResponse> {
  return getJson<GeographicHeatmapResponse>(
    `${API_BASE_URL}/api/v1/ic3/analytics/geographic-heatmap`,
    signal
  )
}

export async function fetchSeverityDistribution(signal: AbortSignal): Promise<SeverityDistributionResponse> {
  return getJson<SeverityDistributionResponse>(
    `${API_BASE_URL}/api/v1/nvd/analytics/severity-distribution`,
    signal
  )
}

export async function fetchSectorAttackMatrix(signal: AbortSignal): Promise<SectorAttackMatrixResponse> {
  return getJson<SectorAttackMatrixResponse>(
    `${API_BASE_URL}/api/v1/ic3/analytics/sector-attack-matrix`,
    signal
  )
}
