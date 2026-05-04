/**
 * API client for the SMB parameterized risk score endpoint.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

export interface AttackExposureItem {
  attack_type: string;
  sector_weight: number;
  contribution: number;
}

export interface IndustryExposureDetail {
  sector: string | null;
  items: AttackExposureItem[];
  industry_score: number;
}

export interface SizeFactorDetail {
  employee_range: string;
  incident_rate: number;
  size_score: number;
}

export interface ScoreComponent {
  name: string;
  score: number;
  weight: number;
  weighted_score: number;
}

export interface RemediatedItem {
  stable_key: string;
  title: string;
  severity: string;
}

export interface RemediationCredit {
  done_count: number;
  raw_points: number;
  applied_points: number;
  items: RemediatedItem[];
}

export interface SmbRiskScore {
  score: number;
  effective_score: number;
  remediation_credit: RemediationCredit;
  industry_exposure: IndustryExposureDetail;
  size_factor: SizeFactorDetail;
  breakdown: ScoreComponent[];
  methodology: string;
  generated_at: string;
}

export function fetchSmbRiskScore(signal: AbortSignal): Promise<SmbRiskScore> {
  return getJsonAuth<SmbRiskScore>(
    `${API_BASE_URL}/api/v1/organizations/mine/risk`,
    signal,
  );
}
