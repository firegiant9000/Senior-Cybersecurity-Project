/**
 * API client for the Assessment Readiness endpoint.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

export interface ReadinessItem {
  key: string;
  label: string;
  complete: boolean;
  required: boolean;
  detail: string;
}

export interface AssessmentReadiness {
  is_ready: boolean;
  readiness_pct: number;
  tier: string;
  items: ReadinessItem[];
  next_steps: string[];
}

export function fetchAssessmentReadiness(
  signal: AbortSignal,
): Promise<AssessmentReadiness> {
  return getJsonAuth<AssessmentReadiness>(
    `${API_BASE_URL}/api/v1/organizations/mine/readiness`,
    signal,
  );
}
