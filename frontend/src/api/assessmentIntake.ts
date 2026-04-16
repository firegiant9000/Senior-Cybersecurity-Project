/**
 * API client for the graduated Assessment Intake tier system.
 */

import { API_BASE_URL, getJsonAuth } from "./fetchWithAuth";

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
