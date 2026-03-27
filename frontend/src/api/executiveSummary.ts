/**
 * API client for the organization executive summary endpoint.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

export interface TopThreat {
  name: string;
  complaint_count: number;
  total_loss: number;
}

export interface ExecutiveSummary {
  risk_score: number;
  risk_label: "Low" | "Medium" | "High" | "Critical";
  top_threats: TopThreat[];
  loss_estimate: number;
  loss_estimate_formatted: string;
  critical_cve_count: number;
  kev_count: number;
  methodology: string;
  confidence_level: "High" | "Medium" | "Low";
  disclaimer: string;
  generated_at: string;
  data_year_range: string;
}

export function fetchExecutiveSummary(
  signal: AbortSignal,
): Promise<ExecutiveSummary> {
  return getJsonAuth<ExecutiveSummary>(
    `${API_BASE_URL}/api/v1/organizations/mine/executive-summary`,
    signal,
  );
}
