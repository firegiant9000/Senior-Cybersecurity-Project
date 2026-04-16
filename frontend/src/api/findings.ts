/**
 * API client for the Findings Engine endpoint.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";
import type { DisclaimerBlock } from "../types/disclaimer";

export interface Finding {
  id: string;
  finding_type: string;
  severity: string;
  severity_score: number | null;
  title: string;
  description: string;
  evidence: Record<string, unknown>;
  source: string;
  affected_assets: string[];
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
