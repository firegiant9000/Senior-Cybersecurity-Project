/**
 * API client for vendor-matched vulnerability alerts.
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export interface VendorAlert {
  vendor_name: string;
  org_product: string;
  cve_id: string;
  kev_product: string;
  due_date: string | null;
  description: string;
  cvss_score: number | null;
  severity_label: string;
  risk_score: number | null;
  published_date: string | null;
}

export interface SeverityBreakdown {
  critical: number;
  high: number;
  medium: number;
  low: number;
  unknown: number;
}

export interface VendorAlertsResponse {
  total_matched: number;
  severity_breakdown: SeverityBreakdown;
  items: VendorAlert[];
  page: number;
  page_size: number;
  unmatched_vendors: string[];
  reason: string | null;
  kev_last_ingest_at: string | null;
}

export async function fetchVendorAlerts(
  page = 1,
  pageSize = 20,
): Promise<VendorAlertsResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/mine/vendor-alerts?page=${page}&page_size=${pageSize}`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to fetch vendor alerts",
    );
  }
  return resp.json();
}
