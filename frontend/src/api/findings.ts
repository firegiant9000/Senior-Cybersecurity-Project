/**
 * API client for the Findings Engine endpoint.
 */

import { API_BASE_URL, fetchWithAuth, getJsonAuth } from "./fetchWithAuth";
import type { DisclaimerBlock } from "../types/disclaimer";

export type FindingStatus = "open" | "done" | "dismissed";

export interface Finding {
  id: string;
  // Identity that survives engine re-ingest. PATCH endpoint keys off this,
  // not `id`, so user-set status persists across snapshots.
  stable_key: string;
  finding_type: string;
  severity: string;
  severity_score: number | null;
  title: string;
  description: string;
  evidence: Record<string, unknown>;
  source: string;
  affected_assets: string[];
  status: FindingStatus;
}

export interface FindingsSummary {
  total: number;
  by_type: Record<string, number>;
  by_severity: Record<string, number>;
}

export interface FindingsReport {
  org_id: number;
  findings: Finding[];
  summary: FindingsSummary;
  generated_at: string;
  data_sources_used: string[];
  assessment_tier: string;
  disclaimer_block?: DisclaimerBlock;
}

export interface SnapshotListItem {
  id: number;
  generated_at: string;
  assessment_tier: string;
  summary: FindingsSummary;
  data_sources_used: string[];
}

export interface SnapshotListResponse {
  items: SnapshotListItem[];
  total: number;
}

export function fetchFindings(signal: AbortSignal): Promise<FindingsReport> {
  return getJsonAuth<FindingsReport>(
    `${API_BASE_URL}/api/v1/organizations/mine/findings`,
    signal,
  );
}

export function fetchFindingsHistory(
  signal: AbortSignal,
  limit = 10,
): Promise<SnapshotListResponse> {
  return getJsonAuth<SnapshotListResponse>(
    `${API_BASE_URL}/api/v1/organizations/mine/findings/history?limit=${limit}`,
    signal,
  );
}

export async function patchFindingStatus(
  stableKey: string,
  status: FindingStatus,
  meta?: { title?: string; severity?: string },
): Promise<{ stable_key: string; status: FindingStatus }> {
  const url = `${API_BASE_URL}/api/v1/organizations/mine/findings/${encodeURIComponent(
    stableKey,
  )}/status`;
  const resp = await fetchWithAuth(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      status,
      title: meta?.title,
      severity: meta?.severity,
    }),
  });
  if (!resp.ok) {
    const text = await resp.text().catch(() => "");
    throw new Error(`Failed to update finding status (${resp.status}): ${text}`);
  }
  return resp.json();
}
