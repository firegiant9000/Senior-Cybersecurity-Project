/**
 * API client for anomaly detection endpoints.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export interface IC3Anomaly {
  sector: string;
  state: string;
  year: number;
  complaint_count: number;
  loss_amount: number;
  z_score_complaints: number;
  z_score_loss: number;
  anomaly_type: "complaints" | "loss" | "both";
}

export interface IC3AnomalyResponse {
  items: IC3Anomaly[];
  threshold: number;
  total: number;
}

export interface TrendAnomaly {
  sector: string;
  year: number;
  complaint_count: number;
  loss_amount: number;
  prev_complaint_count: number | null;
  prev_loss_amount: number | null;
  yoy_change_complaints: number | null;
  yoy_change_loss: number | null;
  flagged: boolean;
}

export interface TrendAnomalyResponse {
  items: TrendAnomaly[];
  threshold_pct: number;
}

export interface VendorExposureAnomaly {
  vendor_name: string;
  kev_match_count: number;
  global_avg_matches: number;
  z_score: number;
  anomaly: boolean;
}

export interface VendorAnomalyResponse {
  items: VendorExposureAnomaly[];
  org_total_matches: number;
  global_avg_total: number;
  threshold: number;
  has_vendors: boolean;
}

export async function fetchIC3Anomalies(
  threshold = 2.0,
): Promise<IC3AnomalyResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/anomalies/ic3?threshold=${threshold}`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to fetch IC3 anomalies",
    );
  }
  return resp.json();
}

export async function fetchTrendAnomalies(
  thresholdPct = 0.5,
): Promise<TrendAnomalyResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/anomalies/trends?threshold_pct=${thresholdPct}`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        "Failed to fetch trend anomalies",
    );
  }
  return resp.json();
}

export async function fetchVendorAnomalies(
  threshold = 2.0,
): Promise<VendorAnomalyResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/anomalies/vendors?threshold=${threshold}`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        "Failed to fetch vendor anomalies",
    );
  }
  return resp.json();
}
