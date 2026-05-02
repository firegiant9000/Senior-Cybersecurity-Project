/**
 * API client for the graduated Assessment Intake tier system.
 */

import { API_BASE_URL, fetchWithAuth, getJsonAuth } from "./fetchWithAuth";

export type AssessmentTier = "incomplete" | "basic" | "enhanced" | "comprehensive";

export interface TierRequirement {
  key: string;
  label: string;
  met: boolean;
  detail: string;
}

export interface TierDefinition {
  tier: AssessmentTier;
  label: string;
  description: string;
  requirements: TierRequirement[];
  all_met: boolean;
  unlocks: string[];
}

export interface AssessmentIntakeResponse {
  current_tier: AssessmentTier;
  tiers: TierDefinition[];
  next_tier: AssessmentTier | null;
  next_tier_progress: number;
  fields_to_advance: string[];
}

export function fetchAssessmentIntake(
  signal: AbortSignal,
): Promise<AssessmentIntakeResponse> {
  return getJsonAuth<AssessmentIntakeResponse>(
    `${API_BASE_URL}/api/v1/organizations/mine/intake`,
    signal,
  );
}

export interface AssessmentIntakePreviewRequest {
  name?: string | null;
  industry_label?: string | null;
  primary_state?: string | null;
  employee_range?: string | null;
  revenue_range?: string | null;
  primary_domain?: string | null;
  primary_vendor?: string | null;
  security_controls?: Record<string, "yes" | "no" | "unsure"> | null;
  compliance_frameworks?: string[] | null;
  data_types?: string[] | null;
}

export async function previewAssessmentIntake(
  payload: AssessmentIntakePreviewRequest,
  signal: AbortSignal,
): Promise<AssessmentIntakeResponse> {
  const resp = await fetchWithAuth(
    `${API_BASE_URL}/api/v1/organizations/mine/intake-preview`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal,
    },
  );
  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(
      (body as { detail?: string }).detail ??
        `Request failed: ${resp.statusText}`,
    );
  }
  return resp.json() as Promise<AssessmentIntakeResponse>;
}
