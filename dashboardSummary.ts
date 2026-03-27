/**
 * Dashboard summary API client.
 * Fetches all data needed for the Overview tab widgets.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

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

// ─── API calls ────────────────────────────────────────────────────────────────

export async function fetchDashboardSummary(): Promise<DashboardSummary> {
  return getJsonAuth<DashboardSummary>(
    `${API_BASE_URL}/api/v1/ic3/analytics/dashboard-summary`
  )
}

export async function fetchAttackTypes(): Promise<AttackTypeListResponse> {
  return getJsonAuth<AttackTypeListResponse>(
    `${API_BASE_URL}/api/v1/ic3/analytics/attack-types`
  )
}

export async function fetchIndustryRisk(): Promise<IndustryRiskResponse> {
  return getJsonAuth<IndustryRiskResponse>(
    `${API_BASE_URL}/api/v1/ic3/analytics/industry-risk`
  )
}

export async function fetchGeographicHeatmap(): Promise<GeographicHeatmapResponse> {
  return getJsonAuth<GeographicHeatmapResponse>(
    `${API_BASE_URL}/api/v1/ic3/analytics/geographic-heatmap`
  )
}

export async function fetchSeverityDistribution(): Promise<SeverityDistributionResponse> {
  return getJsonAuth<SeverityDistributionResponse>(
    `${API_BASE_URL}/api/v1/nvd/analytics/severity-distribution`
  )
}

export async function fetchSectorAttackMatrix(): Promise<SectorAttackMatrixResponse> {
  return getJsonAuth<SectorAttackMatrixResponse>(
    `${API_BASE_URL}/api/v1/ic3/analytics/sector-attack-matrix`
  )
}
