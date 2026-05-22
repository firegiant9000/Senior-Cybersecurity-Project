/**
 * API client for org assets + per-asset software (Month 2 Phase C).
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export type DiscoveredVia = "csv_upload" | "m365" | "gws" | "agent" | "manual";

export interface Asset {
  id: number;
  org_id: number;
  hostname: string;
  ip_address: string | null;
  os_name: string | null;
  os_version: string | null;
  mac_address: string | null;
  discovered_via: DiscoveredVia;
  first_seen: string;
  last_seen: string;
  is_active: boolean;
  metadata: Record<string, unknown> | null;
  tags: string[] | null;
  created_by_scan_run_id: number | null;
  created_at: string;
  updated_at: string;
  source: string;
}

export interface AssetWithKev {
  asset: Asset;
  kev_match_count: number;
}

export interface AssetListResponse {
  total: number;
  page: number;
  page_size: number;
  items: AssetWithKev[];
}

export interface AssetSoftware {
  id: number;
  asset_id: number;
  org_id: number;
  vendor: string;
  product: string;
  version: string | null;
  cpe_uri: string | null;
  source: DiscoveredVia;
  first_seen: string;
  last_seen: string;
  created_at: string;
}

export interface AssetDetailResponse {
  asset: Asset;
  software: AssetSoftware[];
}

export async function listAssets(
  orgId: number,
  opts: {
    page?: number;
    pageSize?: number;
    isActive?: boolean;
    vendor?: string;
    hostname?: string;
  } = {},
): Promise<AssetListResponse> {
  const params = new URLSearchParams();
  params.set("page", String(opts.page ?? 1));
  params.set("page_size", String(opts.pageSize ?? 50));
  if (opts.isActive !== undefined) params.set("is_active", String(opts.isActive));
  if (opts.vendor) params.set("vendor", opts.vendor);
  if (opts.hostname) params.set("hostname", opts.hostname);
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/assets?${params}`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? "Failed to load assets");
  }
  return resp.json();
}

export async function getAsset(
  orgId: number,
  assetId: number,
): Promise<AssetDetailResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/assets/${assetId}`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? "Failed to load asset");
  }
  return resp.json();
}

export interface AssetFindingMatch {
  software_id: number;
  vendor: string;
  product: string;
  version: string | null;
  cve_id: string;
  cvss_score: number | null;
  severity: string | null;
  in_kev: boolean;
  description: string | null;
}

export interface AssetFindingsResponse {
  asset_id: number;
  total: number;
  items: AssetFindingMatch[];
  note: string;
}

export async function setAssetTags(
  orgId: number,
  assetId: number,
  tags: string[],
): Promise<Asset> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/assets/${assetId}/tags`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ tags }),
    },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? "Failed to save tags");
  }
  return resp.json();
}

export interface AssetRiskRow {
  asset_id: number;
  hostname: string;
  max_cvss: number | null;
  max_epss_percentile: number | null;
  risk_score: number;
  in_kev: boolean;
}

export interface AssetRiskSummary {
  org_id: number;
  items: AssetRiskRow[];
  note: string;
  source: string;
}

export async function getAssetRiskSummary(
  orgId: number,
  limit = 5,
): Promise<AssetRiskSummary> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/inventory/risk-summary?limit=${limit}`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to load risk summary",
    );
  }
  return resp.json();
}

export async function getAssetFindings(
  orgId: number,
  assetId: number,
): Promise<AssetFindingsResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/assets/${assetId}/findings`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to load asset findings",
    );
  }
  return resp.json();
}

export interface VendorAssetCount {
  vendor: string;
  asset_count: number;
}

export interface InventoryHealth {
  assets_total: number;
  assets_with_known_software: number;
  assets_with_kev_match: number;
  last_inventory_update: string | null;
  last_source: string | null;
  top_vendors: VendorAssetCount[];
  source: string;
}

export async function getInventoryHealth(orgId: number): Promise<InventoryHealth> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/inventory/health`,
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ?? "Failed to load inventory health",
    );
  }
  return resp.json();
}
