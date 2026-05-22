/**
 * API client for CSV inventory upload + scan-run polling (Month 2 Phase C).
 */

import { API_BASE_URL, fetchWithAuth } from "./fetchWithAuth";

export interface CsvRowError {
  row_number: number;
  errors: string[];
}

export interface CsvPreviewResponse {
  valid_rows: number;
  invalid_rows: CsvRowError[];
  distinct_assets: number;
  distinct_software: number;
  would_create: number;
  would_update: number;
}

export interface ScanRun {
  id: number;
  org_id: number;
  source: "csv_upload" | "m365" | "gws" | "agent";
  status: "pending" | "running" | "succeeded" | "failed" | "partial";
  started_at: string;
  finished_at: string | null;
  asset_count: number;
  software_count: number;
  error_message: string | null;
  metadata: Record<string, unknown> | null;
  triggered_by_user_id: number | null;
}

export interface ScanRunListResponse {
  total: number;
  page: number;
  page_size: number;
  items: ScanRun[];
}

async function readErr(resp: Response, fallback: string): Promise<string> {
  const body = await resp.json().catch(() => ({}));
  return (body as { detail?: string }).detail ?? fallback;
}

export async function previewInventoryCsv(
  orgId: number,
  file: File,
): Promise<CsvPreviewResponse> {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/inventory/uploads/csv/preview`,
    { method: "POST", body: fd },
  );
  if (!resp.ok) throw new Error(await readErr(resp, "Failed to preview CSV"));
  return resp.json();
}

export async function importInventoryCsv(
  orgId: number,
  file: File,
): Promise<ScanRun> {
  const fd = new FormData();
  fd.append("file", file);
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/inventory/uploads/csv/import?confirm=true`,
    { method: "POST", body: fd },
  );
  if (!resp.ok) throw new Error(await readErr(resp, "Failed to import CSV"));
  return resp.json();
}

export async function getScanRun(
  orgId: number,
  scanRunId: number,
): Promise<ScanRun> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/scan-runs/${scanRunId}`,
  );
  if (!resp.ok) throw new Error(await readErr(resp, "Failed to load scan run"));
  return resp.json();
}

export interface ScanRunDiff {
  scan_run_id: number;
  previous_scan_run_id: number | null;
  assets_added: number;
  assets_refreshed: number;
  software_added: number;
  note: string;
}

export async function getScanRunDiff(
  orgId: number,
  scanRunId: number,
): Promise<ScanRunDiff> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/scan-runs/${scanRunId}/diff`,
  );
  if (!resp.ok) throw new Error(await readErr(resp, "Failed to load diff"));
  return resp.json();
}

export interface ScanRunRollbackResponse {
  scan_run_id: number;
  assets_deleted: number;
  software_deleted: number;
  note: string;
}

export async function rollbackScanRun(
  orgId: number,
  scanRunId: number,
): Promise<ScanRunRollbackResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/scan-runs/${scanRunId}/rollback`,
    { method: "POST" },
  );
  if (!resp.ok) throw new Error(await readErr(resp, "Failed to rollback"));
  return resp.json();
}

export async function listScanRuns(
  orgId: number,
  page = 1,
  pageSize = 20,
): Promise<ScanRunListResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/${orgId}/scan-runs?page=${page}&page_size=${pageSize}`,
  );
  if (!resp.ok) throw new Error(await readErr(resp, "Failed to load scan history"));
  return resp.json();
}
