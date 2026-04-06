/**
 * API client for the organization loss projection endpoint.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

export interface LossProjection {
  projected_annual_loss: number;
  projected_annual_loss_formatted: string;
  sector: string;
  state: string;
  employee_range: string;
  size_multiplier: number;
  ic3_avg_loss_per_incident: number | null;
  ic3_incident_count: number | null;
  ic3_data_years: string | null;
  confidence_level: "High" | "Medium" | "Low";
  methodology: string;
  has_data: boolean;
  generated_at: string;
}

export function fetchLossProjection(signal: AbortSignal): Promise<LossProjection> {
  return getJsonAuth<LossProjection>(
    `${API_BASE_URL}/api/v1/organizations/mine/loss-projection`,
    signal,
  );
}
