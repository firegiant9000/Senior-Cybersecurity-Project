/**
 * API client for the AI Executive Summary endpoint.
 */

import { API_BASE_URL, fetchWithAuth, getJsonAuth } from "./fetchWithAuth";

export interface AISummaryResponse {
  narrative: string;
  ai_generated: boolean;
  model_used: string | null;
  findings_count: number;
  risk_score: number;
  risk_label: string;
  generated_at: string;
  cached: boolean;
  disclaimer: string;
}

export interface FeedbackRequest {
  rating: number;
  flag: "helpful" | "inaccurate" | "too_vague" | "other";
  comment?: string;
}

export interface FeedbackResponse {
  id: number;
  rating: number;
  flag: string;
  comment: string | null;
  created_at: string;
}

export function fetchAISummary(
  signal: AbortSignal,
): Promise<AISummaryResponse> {
  return getJsonAuth<AISummaryResponse>(
    `${API_BASE_URL}/api/v1/organizations/mine/ai-summary`,
    signal,
  );
}

export async function submitFeedback(
  body: FeedbackRequest,
): Promise<FeedbackResponse> {
  const response = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/mine/ai-summary/feedback`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      (data as { detail?: string }).detail ?? `Request failed: ${response.statusText}`,
    );
  }
  return response.json() as Promise<FeedbackResponse>;
}
