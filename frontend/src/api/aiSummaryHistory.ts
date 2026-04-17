/**
 * API client for AI Summary generation history endpoints.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

export interface AISummaryGenerationListItem {
  id: number;
  org_id: number;
  generated_at: string;
  model_name: string;
  source: string;
  status: string;
  error_message: string | null;
  output_text: string | null;
  latency_ms: number | null;
  findings_snapshot_id: number | null;
}

export interface AISummaryGenerationDetail extends AISummaryGenerationListItem {
  prompt_inputs: Record<string, unknown>;
  rendered_prompt: string | null;
  output_meta: Record<string, unknown> | null;
}

export interface AISummaryGenerationListResponse {
  items: AISummaryGenerationListItem[];
  total: number;
  limit: number;
  offset: number;
}

export function fetchAISummaryHistory(
  signal: AbortSignal,
  limit = 20,
  offset = 0,
): Promise<AISummaryGenerationListResponse> {
  return getJsonAuth<AISummaryGenerationListResponse>(
    `${API_BASE_URL}/api/v1/organizations/mine/ai-summary/history?limit=${limit}&offset=${offset}`,
    signal,
  );
}

export function fetchAISummaryGeneration(
  id: number,
  signal: AbortSignal,
): Promise<AISummaryGenerationDetail> {
  return getJsonAuth<AISummaryGenerationDetail>(
    `${API_BASE_URL}/api/v1/organizations/mine/ai-summary/history/${id}`,
    signal,
  );
}
